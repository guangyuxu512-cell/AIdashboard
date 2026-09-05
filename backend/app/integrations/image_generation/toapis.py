from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from pathlib import PurePosixPath
import re
from tempfile import SpooledTemporaryFile
from time import monotonic, sleep
from typing import Any, BinaryIO, Iterator
from urllib.parse import quote, urlsplit

import httpx
from pydantic import SecretStr

from app.modules.ai_workbench.provider import (
    GeneratedProviderImage,
    GenerationProviderInput,
    GenerationProviderRequest,
    ImageProviderFailure,
    PROVIDER_CREATE_OUTCOME_UNKNOWN_CODE,
    PROVIDER_CREATE_OUTCOME_UNKNOWN_MESSAGE,
)


TOAPIS_PROVIDER_CODE = "toapis"
UPLOAD_PATH = "/v1/uploads/images"
GENERATE_PATH = "/v1/images/generations"
SUCCESS_STATUSES = frozenset({"completed", "success", "succeeded"})
FAILURE_STATUSES = frozenset({"failed", "failure", "error"})
RUNNING_STATUSES = frozenset(
    {"pending", "queued", "processing", "running", "in_progress"},
)
SUPPORTED_RESULT_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
CONTENT_TYPE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
DEFINITIVE_CREATE_REJECTION_CODES = frozenset(
    {
        "PROVIDER_AUTHENTICATION_FAILED",
        "PROVIDER_RATE_LIMITED",
        "PROVIDER_REQUEST_REJECTED",
    },
)


class ToApisImageProvider:
    provider_code = TOAPIS_PROVIDER_CODE

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str,
        model_code: str,
        resolution: str,
        quality: str,
        poll_interval_seconds: float,
        poll_timeout_seconds: float,
        request_timeout_seconds: float,
        max_output_bytes: int,
        client: httpx.Client | None = None,
        sleep_fn: Callable[[float], None] = sleep,
        monotonic_fn: Callable[[], float] = monotonic,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model_code = model_code
        self._resolution = resolution
        self._quality = quality
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_timeout_seconds = poll_timeout_seconds
        self._request_timeout_seconds = request_timeout_seconds
        self._max_output_bytes = max_output_bytes
        self._client = client
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn

    def create_task(self, request: GenerationProviderRequest) -> str:
        create_request_started = False
        external_task_id: str | None = None
        try:
            with self._client_scope() as client:
                image_urls = [
                    self._upload_image(client, image)
                    for image in request.input_images
                ]
                body: dict[str, Any] = {
                    "model": self._model_code,
                    "prompt": request.final_prompt,
                    "size": request.size.value,
                    "resolution": self._resolution,
                    "quality": self._quality,
                    "n": 1,
                    "response_format": "url",
                }
                if image_urls:
                    body["image_urls"] = image_urls
                create_request_started = True
                payload = self._request_json(
                    client,
                    "POST",
                    f"{self._base_url}{GENERATE_PATH}",
                    json=body,
                )
                external_task_id = _task_id(payload)
        except ImageProviderFailure as error:
            if (
                not create_request_started
                or error.failure_code in DEFINITIVE_CREATE_REJECTION_CODES
            ):
                raise
            raise _create_outcome_unknown_failure() from None
        except Exception:
            if create_request_started:
                raise _create_outcome_unknown_failure() from None
            raise
        if external_task_id is None:
            raise _create_outcome_unknown_failure()
        return external_task_id

    def wait_for_image(self, external_task_id: str) -> GeneratedProviderImage:
        started_at = self._monotonic()
        with self._client_scope() as client:
            while True:
                try:
                    payload = self._request_json(
                        client,
                        "GET",
                        (
                            f"{self._base_url}{GENERATE_PATH}/"
                            f"{quote(external_task_id, safe='')}"
                        ),
                    )
                except ImageProviderFailure as error:
                    if not error.retryable:
                        raise
                    if self._monotonic() - started_at >= self._poll_timeout_seconds:
                        raise ImageProviderFailure(
                            "PROVIDER_TIMEOUT",
                            "图片生成服务处理超时",
                            retryable=True,
                        ) from None
                    self._sleep(self._poll_interval_seconds)
                    continue
                task = _task_payload(payload)
                display_response = task.get("display_response")
                status = str(
                    task.get("status")
                    or (
                        display_response.get("status")
                        if isinstance(display_response, dict)
                        else ""
                    )
                    or "",
                ).strip().lower()
                if status in SUCCESS_STATUSES:
                    result_url = _result_url(task)
                    if result_url is None:
                        raise ImageProviderFailure(
                            "PROVIDER_RESPONSE_INVALID",
                            "图片生成服务未返回结果图片",
                            retryable=False,
                        )
                    return self._download_image(client, result_url)
                if status in FAILURE_STATUSES:
                    raise _terminal_failure(task)
                if status not in RUNNING_STATUSES:
                    raise ImageProviderFailure(
                        "PROVIDER_RESPONSE_INVALID",
                        "图片生成服务返回了未知任务状态",
                        retryable=False,
                    )
                if self._monotonic() - started_at >= self._poll_timeout_seconds:
                    raise ImageProviderFailure(
                        "PROVIDER_TIMEOUT",
                        "图片生成服务处理超时",
                        retryable=True,
                    )
                self._sleep(self._poll_interval_seconds)

    def _upload_image(
        self,
        client: httpx.Client,
        image: GenerationProviderInput,
    ) -> str:
        payload = self._request_json(
            client,
            "POST",
            f"{self._base_url}{UPLOAD_PATH}",
            files={
                "file": (
                    image.original_filename,
                    image.stream,
                    image.content_type,
                ),
            },
            data={"purpose": "generation"},
        )
        data = payload.get("data")
        uploaded_url = data.get("url") if isinstance(data, dict) else None
        if not isinstance(uploaded_url, str) or not uploaded_url.strip():
            raise ImageProviderFailure(
                "PROVIDER_RESPONSE_INVALID",
                "图片生成服务未返回上传结果",
                retryable=False,
            )
        return uploaded_url.strip()

    def _download_image(
        self,
        client: httpx.Client,
        result_url: str,
    ) -> GeneratedProviderImage:
        _validate_result_url(result_url)
        try:
            with client.stream(
                "GET",
                result_url,
                timeout=self._request_timeout_seconds,
                follow_redirects=False,
            ) as response:
                self._raise_for_status(response)
                content_type = _normalized_content_type(
                    response.headers.get("content-type"),
                )
                suffix = _result_suffix(result_url, content_type)
                stream = SpooledTemporaryFile(max_size=self._max_output_bytes)
                size = 0
                try:
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > self._max_output_bytes:
                            raise ImageProviderFailure(
                                "PROVIDER_OUTPUT_INVALID",
                                "生成图片超过文件大小限制",
                                retryable=False,
                            )
                        stream.write(chunk)
                    if size == 0:
                        raise ImageProviderFailure(
                            "PROVIDER_OUTPUT_INVALID",
                            "图片生成服务返回了空文件",
                            retryable=False,
                        )
                    stream.seek(0)
                    return GeneratedProviderImage(
                        original_filename=f"generated{suffix}",
                        content_type=content_type,
                        stream=stream,
                    )
                except Exception:
                    stream.close()
                    raise
        except ImageProviderFailure:
            raise
        except httpx.TimeoutException:
            raise ImageProviderFailure(
                "PROVIDER_TIMEOUT",
                "生成图片下载超时",
                retryable=True,
            ) from None
        except httpx.RequestError:
            raise ImageProviderFailure(
                "PROVIDER_UNAVAILABLE",
                "生成图片下载失败",
                retryable=True,
            ) from None

    def _request_json(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            response = client.request(
                method,
                url,
                headers=self._authorization_headers(),
                timeout=self._request_timeout_seconds,
                follow_redirects=False,
                **kwargs,
            )
            self._raise_for_status(response)
            payload = response.json()
        except ImageProviderFailure:
            raise
        except httpx.TimeoutException:
            raise ImageProviderFailure(
                "PROVIDER_TIMEOUT",
                "图片生成服务请求超时",
                retryable=True,
            ) from None
        except httpx.RequestError:
            raise ImageProviderFailure(
                "PROVIDER_UNAVAILABLE",
                "图片生成服务暂时不可用",
                retryable=True,
            ) from None
        except ValueError:
            raise ImageProviderFailure(
                "PROVIDER_RESPONSE_INVALID",
                "图片生成服务返回了无效响应",
                retryable=False,
            ) from None
        if not isinstance(payload, dict):
            raise ImageProviderFailure(
                "PROVIDER_RESPONSE_INVALID",
                "图片生成服务返回了无效响应",
                retryable=False,
            )
        return payload

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {401, 403}:
            failure = ImageProviderFailure(
                "PROVIDER_AUTHENTICATION_FAILED",
                "图片生成服务认证失败",
                retryable=False,
            )
        elif response.status_code == 429:
            failure = ImageProviderFailure(
                "PROVIDER_RATE_LIMITED",
                "图片生成服务请求过于频繁",
                retryable=True,
            )
        elif response.status_code in {408, 409, 425, 500, 502, 503, 504}:
            failure = ImageProviderFailure(
                "PROVIDER_UNAVAILABLE",
                "图片生成服务暂时不可用",
                retryable=True,
            )
        else:
            failure = ImageProviderFailure(
                "PROVIDER_REQUEST_REJECTED",
                "图片生成服务拒绝了请求",
                retryable=False,
            )
        raise failure

    def _authorization_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key.get_secret_value()}",
        }

    @contextmanager
    def _client_scope(self) -> Iterator[httpx.Client]:
        if self._client is not None:
            yield self._client
            return
        with httpx.Client(
            timeout=self._request_timeout_seconds,
            follow_redirects=False,
        ) as client:
            yield client


def _task_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    candidates = [
        payload.get("id"),
        payload.get("task_id"),
        data.get("id") if isinstance(data, dict) else None,
        data.get("task_id") if isinstance(data, dict) else None,
    ]
    for value in candidates:
        if isinstance(value, bool):
            continue
        if isinstance(value, (str, int)):
            normalized = str(value).strip()
            if normalized and len(normalized) <= 255 and not normalized.isspace():
                return normalized
    return None


def _create_outcome_unknown_failure() -> ImageProviderFailure:
    return ImageProviderFailure(
        PROVIDER_CREATE_OUTCOME_UNKNOWN_CODE,
        PROVIDER_CREATE_OUTCOME_UNKNOWN_MESSAGE,
        retryable=False,
    )


def _task_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list) and items and isinstance(items[0], dict):
            return items[0]
        if "status" in data:
            return data
    return payload


def _result_url(task: dict[str, Any]) -> str | None:
    result = task.get("result")
    if not isinstance(result, dict):
        return None
    data = result.get("data")
    if not isinstance(data, list):
        return None
    for item in data:
        if isinstance(item, dict) and isinstance(item.get("url"), str):
            value = item["url"].strip()
            if value:
                return value
    return None


def _terminal_failure(task: dict[str, Any]) -> ImageProviderFailure:
    error = task.get("error")
    if not isinstance(error, dict):
        error = {}
    failure_code = _safe_failure_code(error.get("code"))
    return ImageProviderFailure(
        failure_code,
        _terminal_failure_message(failure_code),
        retryable=False,
    )


def _safe_failure_code(value: Any) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip(
        "_",
    )
    return {
        "CONTENT_POLICY": "PROVIDER_CONTENT_POLICY",
    }.get(normalized, "PROVIDER_FAILED")


def _terminal_failure_message(failure_code: str) -> str:
    if failure_code == "PROVIDER_CONTENT_POLICY":
        return "图片生成请求未通过内容检查"
    return "图片生成失败"


def _validate_result_url(value: str) -> None:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    trusted_host = hostname in {"toapis.com", "toapis.cn"} or hostname.endswith(
        (".toapis.com", ".toapis.cn"),
    )
    try:
        port = parsed.port
    except ValueError:
        port = -1
    if (
        parsed.scheme != "https"
        or not trusted_host
        or parsed.username is not None
        or parsed.password is not None
        or port not in {None, 443}
    ):
        raise ImageProviderFailure(
            "PROVIDER_OUTPUT_INVALID",
            "图片生成服务返回了不受信任的结果地址",
            retryable=False,
        )


def _normalized_content_type(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.split(";", 1)[0].strip().lower()
    return normalized if normalized in CONTENT_TYPE_SUFFIXES else None


def _result_suffix(result_url: str, content_type: str | None) -> str:
    if content_type is not None:
        return CONTENT_TYPE_SUFFIXES[content_type]
    suffix = PurePosixPath(urlsplit(result_url).path).suffix.lower()
    return suffix if suffix in SUPPORTED_RESULT_SUFFIXES else ".png"
