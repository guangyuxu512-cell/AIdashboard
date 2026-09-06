from __future__ import annotations

from contextlib import nullcontext
from dataclasses import replace
from io import BytesIO
import json
import logging
from typing import Any
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import Settings
from app.core.logging import configure_dependency_logging
from app.integrations.image_generation.toapis import ToApisImageProvider
from app.modules.ai_workbench.enums import (
    GenerationMode,
    GenerationSize,
    OutputFormat,
    OutputRole,
)
from app.modules.ai_workbench.exceptions import (
    GenerationItemStateConflictError,
    ProviderCreateOutcomeUnknownError,
)
from app.modules.ai_workbench.generation_executor import GenerationExecutor
from app.modules.ai_workbench.generation_service import (
    GenerationExecution,
    GenerationExecutionInput,
)
from app.modules.ai_workbench.provider import (
    GeneratedProviderImage,
    GenerationProviderInput,
    GenerationProviderRequest,
    ImageProviderFailure,
    PROVIDER_CREATE_OUTCOME_UNKNOWN_CODE,
    PROVIDER_CREATE_OUTCOME_UNKNOWN_MESSAGE,
)
from app.modules.assets.storage import StoredAsset


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + (b"provider-result" * 4)
SECRET = "unit-test-secret-never-log"


def provider_request(
    *,
    mode: GenerationMode = GenerationMode.NORMAL_GENERATION,
    output_format: OutputFormat = OutputFormat.SINGLE,
) -> GenerationProviderRequest:
    return GenerationProviderRequest(
        generation_item_id=uuid4(),
        model_code="gpt-image-2",
        mode=mode,
        final_prompt="保持这段完整提示词，不做拼接 {{literal}}",
        output_role=OutputRole.MAIN_IMAGE,
        output_format=output_format,
        size=GenerationSize.SQUARE,
        input_images=(
            GenerationProviderInput(
                asset_id=uuid4(),
                original_filename="source.png",
                content_type="image/png",
                stream=BytesIO(PNG_BYTES),
            ),
        ),
    )


def toapis_provider(
    client: httpx.Client,
    *,
    sleep_fn: Any = lambda _seconds: None,
) -> ToApisImageProvider:
    return ToApisImageProvider(
        api_key=SecretStr(SECRET),
        base_url="https://toapis.com",
        resolution="2k",
        quality="low",
        poll_interval_seconds=0,
        poll_timeout_seconds=180,
        request_timeout_seconds=180,
        max_output_bytes=1024 * 1024,
        client=client,
        sleep_fn=sleep_fn,
    )


@pytest.mark.parametrize(
    ("mode", "output_format"),
    [
        (GenerationMode.NORMAL_GENERATION, OutputFormat.SINGLE),
        (GenerationMode.STYLE_REPLICATION, OutputFormat.COLLAGE_2X2),
    ],
)
def test_toapis_upload_create_poll_and_download_use_verified_contract(
    mode: GenerationMode,
    output_format: OutputFormat,
) -> None:
    calls: list[httpx.Request] = []
    statuses = ["running", "completed"]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.host == "toapis.com":
            assert request.headers["authorization"] == f"Bearer {SECRET}"
        if request.url.path == "/v1/uploads/images":
            assert request.method == "POST"
            assert b'name="purpose"' in request.content
            assert b"generation" in request.content
            return httpx.Response(
                200,
                json={"data": {"url": "https://files.toapis.com/input.png"}},
            )
        if request.url.path == "/v1/images/generations":
            assert request.method == "POST"
            assert "idempotency-key" not in request.headers
            body = json.loads(request.content)
            assert body == {
                "model": "gpt-image-2",
                "prompt": "保持这段完整提示词，不做拼接 {{literal}}",
                "size": "1:1",
                "resolution": "2k",
                "quality": "low",
                "n": 1,
                "response_format": "url",
                "image_urls": ["https://files.toapis.com/input.png"],
            }
            assert "mode" not in body
            assert "role" not in body
            assert "output_format" not in body
            return httpx.Response(200, json={"data": {"id": "task-001"}})
        if request.url.path == "/v1/images/generations/task-001":
            status = statuses.pop(0)
            task: dict[str, Any] = {"status": status}
            if status == "completed":
                task["result"] = {
                    "data": [
                        {
                            "url": (
                                "https://files.toapis.com/output.png"
                                "?temporary=result-token"
                            ),
                        },
                    ],
                }
            return httpx.Response(200, json={"data": task})
        if request.url.path == "/output.png":
            assert request.method == "GET"
            return httpx.Response(
                200,
                headers={"content-type": "image/png"},
                content=PNG_BYTES,
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url.path}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = toapis_provider(client)
        task_id = provider.create_task(
            provider_request(mode=mode, output_format=output_format),
        )
        image = provider.wait_for_image(task_id)
        try:
            assert task_id == "task-001"
            assert image.original_filename == "generated.png"
            assert image.content_type == "image/png"
            assert image.stream.read() == PNG_BYTES
        finally:
            image.stream.close()

    assert [request.url.path for request in calls] == [
        "/v1/uploads/images",
        "/v1/images/generations",
        "/v1/images/generations/task-001",
        "/v1/images/generations/task-001",
        "/output.png",
    ]


@pytest.mark.parametrize(
    "scenario",
    [
        "timeout",
        "connection_lost",
        "invalid_json",
        "missing_task_id",
        "boolean_task_id",
        "http_503",
        "unexpected_exception",
    ],
)
def test_toapis_ambiguous_create_response_fails_with_unknown_outcome(
    scenario: str,
) -> None:
    create_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal create_calls
        if request.url.path == "/v1/uploads/images":
            return httpx.Response(
                200,
                json={"data": {"url": "https://files.toapis.com/input.png"}},
            )
        assert request.url.path == "/v1/images/generations"
        create_calls += 1
        if scenario == "timeout":
            raise httpx.ReadTimeout("ambiguous create timeout", request=request)
        if scenario == "connection_lost":
            raise httpx.ReadError("ambiguous create connection loss", request=request)
        if scenario == "invalid_json":
            return httpx.Response(200, content=b"not-json")
        if scenario == "missing_task_id":
            return httpx.Response(200, json={"data": {"status": "queued"}})
        if scenario == "boolean_task_id":
            return httpx.Response(200, json={"data": {"id": True}})
        if scenario == "unexpected_exception":
            raise RuntimeError("unexpected post-response failure")
        return httpx.Response(503, json={"error": {"code": "unavailable"}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = toapis_provider(client)
        with pytest.raises(ImageProviderFailure) as captured:
            provider.create_task(provider_request())

    assert create_calls == 1
    assert captured.value.failure_code == PROVIDER_CREATE_OUTCOME_UNKNOWN_CODE
    assert captured.value.safe_message == PROVIDER_CREATE_OUTCOME_UNKNOWN_MESSAGE
    assert captured.value.retryable is False


@pytest.mark.parametrize(
    ("status_code", "expected_code", "expected_message"),
    [
        (400, "PROVIDER_REQUEST_REJECTED", "图片生成服务拒绝了请求"),
        (401, "PROVIDER_AUTHENTICATION_FAILED", "图片生成服务认证失败"),
        (429, "PROVIDER_RATE_LIMITED", "图片生成服务请求过于频繁"),
    ],
)
def test_toapis_explicit_create_rejection_remains_an_ordinary_failure(
    status_code: int,
    expected_code: str,
    expected_message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/uploads/images":
            return httpx.Response(
                200,
                json={"data": {"url": "https://files.toapis.com/input.png"}},
            )
        assert request.url.path == "/v1/images/generations"
        return httpx.Response(
            status_code,
            json={"error": {"code": "explicit_rejection"}},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = toapis_provider(client)
        with pytest.raises(ImageProviderFailure) as captured:
            provider.create_task(provider_request())

    assert captured.value.failure_code == expected_code
    assert captured.value.safe_message == expected_message


def test_toapis_upload_failure_is_not_a_create_outcome_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/uploads/images"
        raise httpx.ReadTimeout("upload timeout", request=request)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = toapis_provider(client)
        with pytest.raises(ImageProviderFailure) as captured:
            provider.create_task(provider_request())

    assert captured.value.failure_code == "PROVIDER_TIMEOUT"
    assert captured.value.failure_code != PROVIDER_CREATE_OUTCOME_UNKNOWN_CODE
    assert captured.value.retryable is True


@pytest.mark.parametrize(
    ("provider_code", "expected_code", "expected_message"),
    [
        (
            "content-policy",
            "PROVIDER_CONTENT_POLICY",
            "图片生成请求未通过内容检查",
        ),
        (f"unknown-{SECRET}", "PROVIDER_FAILED", "图片生成失败"),
    ],
)
def test_toapis_terminal_failure_does_not_expose_provider_message(
    provider_code: str,
    expected_code: str,
    expected_message: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/task-failed")
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "failed",
                    "error": {
                        "code": provider_code,
                        "message": (
                            f"rejected {SECRET} "
                            "https://files.toapis.com/input.png?token=url-secret"
                        ),
                    },
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = toapis_provider(client)
        with pytest.raises(ImageProviderFailure) as captured:
            provider.wait_for_image("task-failed")

    assert captured.value.failure_code == expected_code
    assert SECRET not in captured.value.safe_message
    assert "url-secret" not in captured.value.safe_message
    assert captured.value.safe_message == expected_message


def test_toapis_rejects_untrusted_result_url_without_downloading() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            200,
            json={
                "data": {
                    "status": "completed",
                    "result": {"data": [{"url": "https://127.0.0.1/private"}]},
                },
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = toapis_provider(client)
        with pytest.raises(ImageProviderFailure) as captured:
            provider.wait_for_image("task-untrusted")

    assert captured.value.failure_code == "PROVIDER_OUTPUT_INVALID"
    assert calls == 1


def test_toapis_signed_result_url_is_not_written_to_dependency_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    signed_token = "temporary-provider-token"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/task-signed-result"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "status": "completed",
                        "result": {
                            "data": [
                                {
                                    "url": (
                                        "https://files.toapis.cn/output.png"
                                        f"?temporary={signed_token}"
                                    ),
                                },
                            ],
                        },
                    },
                },
            )
        return httpx.Response(
            200,
            headers={"content-type": "image/png"},
            content=PNG_BYTES,
        )

    configure_dependency_logging()
    assert logging.getLogger("httpx").level >= logging.WARNING
    assert logging.getLogger("httpcore").level >= logging.WARNING
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = toapis_provider(client)
        with caplog.at_level(logging.INFO):
            image = provider.wait_for_image("task-signed-result")
        image.stream.close()

    assert signed_token not in caplog.text
    assert "https://files.toapis.cn/output.png" not in caplog.text


def test_toapis_settings_keep_secret_masked_and_require_https_origin() -> None:
    defaults = Settings(_env_file=None)
    assert defaults.toapis_base_url == "https://toapis.cn"
    settings = Settings(
        _env_file=None,
        toapis_api_key=SECRET,
        toapis_base_url="https://toapis.com/",
    )
    assert settings.toapis_base_url == "https://toapis.com"
    assert SECRET not in repr(settings)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, toapis_base_url="http://toapis.com")


class MemoryStorage:
    def __init__(self) -> None:
        self.content = {"input.png": PNG_BYTES}

    def open(self, storage_key: str) -> BytesIO:
        return BytesIO(self.content[storage_key])

    def exists(self, storage_key: str) -> bool:
        return storage_key in self.content

    def store(self, **_kwargs: object) -> StoredAsset:
        raise AssertionError("store is owned by GenerationService in these unit tests")

    def delete(self, storage_key: str) -> None:
        self.content.pop(storage_key, None)


class FakeExecutionService:
    def __init__(
        self,
        executions: list[GenerationExecution],
        events: list[str],
        *,
        record_error: BaseException | None = None,
    ) -> None:
        self.executions = executions
        self.events = events
        self.current_attempt = executions[-1].attempt_count if executions else 1
        self.recorded: list[tuple[int, str]] = []
        self.completed_attempts: list[int] = []
        self.failures: list[tuple[int, str, str]] = []
        self.record_error = record_error

    def prepare_next_provider_execution(self) -> GenerationExecution | None:
        return self.executions.pop(0) if self.executions else None

    def record_provider_execution(
        self,
        _generation_item_id: object,
        *,
        expected_attempt_count: int,
        provider_code: str,
        external_task_id: str,
    ) -> None:
        assert provider_code == "toapis"
        if expected_attempt_count != self.current_attempt:
            raise GenerationItemStateConflictError()
        self.events.append("record")
        if self.record_error is not None:
            raise self.record_error
        self.recorded.append((expected_attempt_count, external_task_id))

    def complete_item(
        self,
        _generation_item_id: object,
        *,
        original_filename: str,
        content_type: str | None,
        stream: BytesIO,
        expected_attempt_count: int,
    ) -> object:
        assert original_filename == "generated.png"
        assert content_type == "image/png"
        assert stream.read() == PNG_BYTES
        if expected_attempt_count != self.current_attempt:
            raise GenerationItemStateConflictError()
        self.events.append("complete")
        self.completed_attempts.append(expected_attempt_count)
        return object()

    def fail_item(
        self,
        _generation_item_id: object,
        *,
        failure_code: str,
        failure_message: str,
        expected_attempt_count: int,
    ) -> object:
        if expected_attempt_count != self.current_attempt:
            raise GenerationItemStateConflictError()
        self.events.append("fail")
        self.failures.append(
            (expected_attempt_count, failure_code, failure_message),
        )
        return object()


class FakeProvider:
    provider_code = "toapis"

    def __init__(
        self,
        outcomes: list[object],
        events: list[str],
        *,
        create_failure: ImageProviderFailure | None = None,
    ) -> None:
        self.outcomes = outcomes
        self.events = events
        self.create_failure = create_failure
        self.created_requests: list[GenerationProviderRequest] = []
        self.waited_task_ids: list[str] = []

    def create_task(self, request: GenerationProviderRequest) -> str:
        self.events.append("create")
        self.created_requests.append(request)
        if self.create_failure is not None:
            raise self.create_failure
        return f"task-attempt-{len(self.created_requests)}"

    def wait_for_image(self, external_task_id: str) -> GeneratedProviderImage:
        self.events.append("wait")
        self.waited_task_ids.append(external_task_id)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[return-value]


def execution(
    *,
    attempt_count: int,
    external_task_id: str | None,
    provider_task_create_required: bool,
    mode: GenerationMode = GenerationMode.NORMAL_GENERATION,
) -> GenerationExecution:
    return GenerationExecution(
        generation_item_id=uuid4(),
        generation_job_id=uuid4(),
        attempt_count=attempt_count,
        team_id=uuid4(),
        created_by_user_id=uuid4(),
        provider_code="toapis",
        model_code="gpt-image-2",
        mode=mode,
        final_prompt="完整 Literal Prompt",
        output_role=OutputRole.MAIN_IMAGE,
        output_format=OutputFormat.SINGLE,
        size=GenerationSize.SQUARE,
        input_assets=(
            GenerationExecutionInput(
                asset_id=uuid4(),
                original_filename="input.png",
                content_type="image/png",
                storage_key="input.png",
            ),
        ),
        external_task_id=external_task_id,
        provider_task_create_required=provider_task_create_required,
    )


def provider_image() -> GeneratedProviderImage:
    return GeneratedProviderImage(
        original_filename="generated.png",
        content_type="image/png",
        stream=BytesIO(PNG_BYTES),
    )


def executor(
    service: FakeExecutionService,
    provider: FakeProvider,
) -> GenerationExecutor:
    return GenerationExecutor(
        session_factory=lambda: nullcontext(object()),  # type: ignore[arg-type]
        service_factory=lambda _session: service,  # type: ignore[arg-type]
        provider=provider,
        storage=MemoryStorage(),
    )


def test_pending_item_creates_and_persists_task_before_polling_then_succeeds() -> None:
    events: list[str] = []
    item = execution(
        attempt_count=1,
        external_task_id=None,
        provider_task_create_required=True,
    )
    service = FakeExecutionService([item], events)
    provider = FakeProvider([provider_image()], events)

    assert executor(service, provider).execute_next() is True

    assert events == ["create", "record", "wait", "complete"]
    assert service.recorded == [(1, "task-attempt-1")]
    assert service.completed_attempts == [1]
    assert provider.created_requests[0].mode is GenerationMode.NORMAL_GENERATION


def test_running_item_resumes_persisted_task_without_duplicate_creation() -> None:
    events: list[str] = []
    item = execution(
        attempt_count=1,
        external_task_id="persisted-task",
        provider_task_create_required=False,
    )
    service = FakeExecutionService([item], events)
    provider = FakeProvider([provider_image()], events)

    assert executor(service, provider).execute_next() is True

    assert provider.created_requests == []
    assert provider.waited_task_ids == ["persisted-task"]
    assert events == ["wait", "complete"]


def test_provider_failure_marks_current_item_failed_with_safe_fields() -> None:
    events: list[str] = []
    item = execution(
        attempt_count=1,
        external_task_id="failed-task",
        provider_task_create_required=False,
    )
    service = FakeExecutionService([item], events)
    provider = FakeProvider(
        [
            ImageProviderFailure(
                "PROVIDER_REJECTED",
                "图片生成服务拒绝了请求",
                retryable=False,
            ),
        ],
        events,
    )

    assert executor(service, provider).execute_next() is True

    assert service.failures == [
        (1, "PROVIDER_REJECTED", "图片生成服务拒绝了请求"),
    ]


def test_retry_replaces_current_task_and_stale_attempt_cannot_write_back() -> None:
    events: list[str] = []
    stale = execution(
        attempt_count=1,
        external_task_id="old-task",
        provider_task_create_required=False,
    )
    retry = replace(
        stale,
        attempt_count=2,
        external_task_id=None,
        provider_task_create_required=True,
    )
    service = FakeExecutionService([stale, retry], events)
    service.current_attempt = 2
    provider = FakeProvider([provider_image(), provider_image()], events)
    runner = executor(service, provider)

    assert runner.execute_next() is True
    assert service.completed_attempts == []
    assert service.failures == []
    assert runner.execute_next() is True

    assert service.recorded == [(2, "task-attempt-1")]
    assert service.completed_attempts == [2]
    assert provider.waited_task_ids == ["old-task", "task-attempt-1"]


def test_unknown_create_outcome_fails_closed_without_duplicate_creation() -> None:
    events: list[str] = []
    item = execution(
        attempt_count=1,
        external_task_id=None,
        provider_task_create_required=False,
    )
    service = FakeExecutionService([item], events)
    provider = FakeProvider([], events)

    assert executor(service, provider).execute_next() is True

    assert provider.created_requests == []
    assert provider.waited_task_ids == []
    assert service.failures == [
        (
            1,
            ProviderCreateOutcomeUnknownError.code,
            ProviderCreateOutcomeUnknownError.message,
        ),
    ]


def test_task_id_persistence_failure_is_recorded_as_unknown_outcome() -> None:
    events: list[str] = []
    item = execution(
        attempt_count=1,
        external_task_id=None,
        provider_task_create_required=True,
    )
    service = FakeExecutionService(
        [item],
        events,
        record_error=RuntimeError("simulated persistence failure"),
    )
    provider = FakeProvider([], events)

    assert executor(service, provider).execute_next() is True

    assert len(provider.created_requests) == 1
    assert provider.waited_task_ids == []
    assert service.failures == [
        (
            1,
            ProviderCreateOutcomeUnknownError.code,
            ProviderCreateOutcomeUnknownError.message,
        ),
    ]


def test_ambiguous_provider_create_failure_is_not_treated_as_retryable() -> None:
    events: list[str] = []
    item = execution(
        attempt_count=1,
        external_task_id=None,
        provider_task_create_required=True,
    )
    service = FakeExecutionService([item], events)
    provider = FakeProvider(
        [],
        events,
        create_failure=ImageProviderFailure(
            PROVIDER_CREATE_OUTCOME_UNKNOWN_CODE,
            PROVIDER_CREATE_OUTCOME_UNKNOWN_MESSAGE,
            retryable=False,
        ),
    )

    assert executor(service, provider).execute_next() is True

    assert len(provider.created_requests) == 1
    assert provider.waited_task_ids == []
    assert service.recorded == []
    assert service.failures == [
        (
            1,
            ProviderCreateOutcomeUnknownError.code,
            ProviderCreateOutcomeUnknownError.message,
        ),
    ]


def test_crash_after_create_does_not_create_again_during_recovery() -> None:
    events: list[str] = []
    item = execution(
        attempt_count=1,
        external_task_id=None,
        provider_task_create_required=True,
    )
    crash_service = FakeExecutionService(
        [item],
        events,
        record_error=SystemExit("simulated process interruption"),
    )
    provider = FakeProvider([provider_image()], events)

    with pytest.raises(SystemExit, match="simulated process interruption"):
        executor(crash_service, provider).execute_next()

    recovered = replace(item, provider_task_create_required=False)
    recovery_service = FakeExecutionService([recovered], events)
    recovery_provider = FakeProvider([], events)
    assert executor(recovery_service, recovery_provider).execute_next() is True

    assert len(provider.created_requests) == 1
    assert recovery_provider.created_requests == []
    assert recovery_service.failures == [
        (
            1,
            ProviderCreateOutcomeUnknownError.code,
            ProviderCreateOutcomeUnknownError.message,
        ),
    ]
