"""HTTP adapter for the existing mobile product-collection gateway.

Only the versioned service-to-service contract lives here.  The adapter never
logs request bodies, response bodies or bearer tokens, and it deliberately
does not expose any of the gateway's device claim APIs.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from enum import StrEnum
from typing import Any, Iterator, Literal
from urllib.parse import quote, urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator

from app.modules.product_collection.contracts import GatewaySettlementV1, Sha256Hex
from app.modules.product_collection.ports import (
    GatewayCancelResult,
    GatewayDispatchCommand,
    GatewayDispatchResult,
)


DISPATCH_PATH = "/api/v1/jobs"
RETRY_PATH = "/api/v1/jobs/retry"
SETTLEMENT_PATH = "/api/v1/control/collection-settlements"
_TERMINAL_CANCEL_CONFLICT = re.compile(
    r"^任务批次或状态已变化，拒绝 canceled 回报（当前状态 (failed|canceled)）$",
)


class GatewayJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    CAPTURED = "captured"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class ProductCollectionGatewayError(RuntimeError):
    """Safe, classified failure returned to the durable retry services."""

    def __init__(
        self,
        failure_code: str,
        safe_message: str,
        *,
        retryable: bool,
        gateway_job_status: Literal["failed", "canceled"] | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.failure_code = failure_code
        self.safe_message = safe_message
        self.retryable = retryable
        self.gateway_job_status = gateway_job_status


class _GatewayDispatchRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    dispatch_id: str = Field(alias="dispatchId", min_length=1, max_length=128)
    gateway_id: str = Field(alias="gatewayId", min_length=1, max_length=128)
    gateway_job_id: str = Field(alias="gatewayJobId", min_length=1, max_length=128)
    external_job_id: str = Field(alias="externalJobId", min_length=1, max_length=128)
    canonical_payload_hash: Sha256Hex = Field(alias="canonicalPayloadHash")
    source_platform: Literal["douyin"] = Field(alias="sourcePlatform")
    source_product_id: str = Field(alias="sourceProductId", min_length=1, max_length=128)
    ingest_mode: Literal["central_ingest_v1"] = Field(alias="ingestMode")
    job_type: Literal["product"] = Field(alias="jobType")
    status: GatewayJobStatus
    reused: bool


class _GatewayDispatchEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[True]
    gateway_id: str = Field(alias="gatewayId", min_length=1, max_length=128)
    requested: Literal[1]
    accepted: tuple[Any, ...]
    accepted_count: int = Field(alias="acceptedCount", ge=0, le=1)
    reused: tuple[Any, ...]
    reused_count: int = Field(alias="reusedCount", ge=0, le=1)
    skipped: tuple[Any, ...]
    skipped_count: int = Field(alias="skippedCount", ge=0, le=1)
    invalid: tuple[Any, ...]
    dispatch: _GatewayDispatchRead

    @model_validator(mode="after")
    def validate_counts(self) -> _GatewayDispatchEnvelope:
        if (
            self.accepted_count != len(self.accepted)
            or self.reused_count != len(self.reused)
            or self.skipped_count != len(self.skipped)
        ):
            raise ValueError("Gateway dispatch result counts do not match")
        if self.accepted_count + self.reused_count != 1:
            raise ValueError("Gateway dispatch must accept or reuse exactly one job")
        if self.skipped_count or self.invalid:
            raise ValueError("Gateway dispatch unexpectedly skipped or rejected the job")
        if self.dispatch.reused != (self.reused_count == 1):
            raise ValueError("Gateway dispatch reuse flag does not match the envelope")
        return self


class _GatewayRetryItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    gateway_job_id: str = Field(alias="gatewayJobId", min_length=1, max_length=128)
    external_job_id: str = Field(alias="externalJobId", min_length=1, max_length=128)
    status: Literal["pending"]
    attempts: int = Field(ge=0)
    max_attempts: int = Field(alias="maxAttempts", ge=1)


class _GatewayRetryEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[True]
    reset: tuple[str, ...]
    items: tuple[_GatewayRetryItem, ...]


class _GatewayCanceledJob(BaseModel):
    # normalizeJob contains existing fields outside this integration contract;
    # only the identity and canceled state are authoritative here.
    model_config = ConfigDict(extra="allow", frozen=True)

    job_id: str = Field(alias="jobId", min_length=1, max_length=128)
    external_job_id: str = Field(alias="externalJobId", min_length=1, max_length=128)
    status: Literal["canceled"]
    capture_batch_id: str | None = Field(default=None, alias="captureBatchId")
    device_id: str | None = Field(default=None, alias="deviceId")
    last_error: Literal["CONTROL_CANCELED"] = Field(alias="lastError")


class _GatewayCancelEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[True]
    job: _GatewayCanceledJob


class _GatewaySettlementRead(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["applied", "duplicate", "superseded"]
    gateway_job_id: str = Field(alias="gatewayJobId", min_length=1, max_length=128)
    capture_batch_id: str = Field(alias="captureBatchId", min_length=1, max_length=128)
    job_status: GatewayJobStatus = Field(alias="jobStatus")


class _GatewaySettlementEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ok: Literal[True]
    settlement: _GatewaySettlementRead


class HttpProductCollectionGateway:
    """Service-authenticated adapter for the already deployed gateway API."""

    def __init__(
        self,
        *,
        base_url: str,
        gateway_id: str,
        control_token: SecretStr | None,
        callback_token: SecretStr | None,
        timeout_seconds: float,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = _validated_base_url(base_url)
        self._gateway_id = _required(gateway_id, "Gateway id")
        self._control_token = _optional_secret(control_token, "Gateway control token")
        self._callback_token = _optional_secret(callback_token, "Gateway callback token")
        if isinstance(timeout_seconds, bool) or timeout_seconds <= 0:
            raise ValueError("Gateway timeout must be positive")
        self._timeout_seconds = float(timeout_seconds)
        self._client = client

    def deliver(self, command: GatewayDispatchCommand) -> GatewayDispatchResult:
        if command.source_platform.value != "douyin":
            raise ProductCollectionGatewayError(
                "PRODUCT_COLLECTION_GATEWAY_REQUEST_INVALID",
                "手机采集网关仅接受已支持的抖音自动任务",
                retryable=False,
            )
        payload = self._request_json(
            "POST",
            DISPATCH_PATH,
            token=_configured_token(self._control_token),
            expected_status=201,
            json=command.payload(),
        )
        try:
            envelope = _GatewayDispatchEnvelope.model_validate(payload)
        except ValidationError:
            raise _invalid_response() from None
        dispatch = envelope.dispatch
        if (
            envelope.gateway_id != self._gateway_id
            or dispatch.gateway_id != self._gateway_id
            or dispatch.dispatch_id != str(command.dispatch_id)
            or dispatch.external_job_id != command.external_job_id
            or dispatch.canonical_payload_hash != command.canonical_payload_hash
            or dispatch.source_platform != command.source_platform.value
            or dispatch.source_product_id != command.source_product_id
            or dispatch.ingest_mode != command.ingest_mode
            or dispatch.job_type != command.job_type
        ):
            raise _invalid_response()
        return GatewayDispatchResult(
            gateway_id=dispatch.gateway_id,
            gateway_job_id=dispatch.gateway_job_id,
            external_job_id=dispatch.external_job_id,
            status=dispatch.status.value,
            reused=dispatch.reused,
        )

    def retry(self, *, gateway_job_id: str) -> GatewayDispatchResult:
        normalized_job_id = _required(gateway_job_id, "Gateway job id")
        payload = self._request_json(
            "POST",
            RETRY_PATH,
            token=_configured_token(self._control_token),
            expected_status=200,
            json={"jobIds": [normalized_job_id]},
        )
        try:
            envelope = _GatewayRetryEnvelope.model_validate(payload)
        except ValidationError:
            raise _invalid_response() from None
        matches = [item for item in envelope.items if item.gateway_job_id == normalized_job_id]
        if tuple(envelope.reset) != (normalized_job_id,) or len(matches) != 1:
            raise ProductCollectionGatewayError(
                "PRODUCT_COLLECTION_GATEWAY_RETRY_REJECTED",
                "手机采集网关未接受该任务的有限重试",
                retryable=False,
            )
        item = matches[0]
        return GatewayDispatchResult(
            gateway_id=self._gateway_id,
            gateway_job_id=item.gateway_job_id,
            external_job_id=item.external_job_id,
            status=item.status,
            reused=True,
        )

    def cancel(self, *, gateway_job_id: str) -> GatewayCancelResult:
        normalized_job_id = _required(gateway_job_id, "Gateway job id")
        try:
            payload = self._request_json(
                "PATCH",
                f"/api/v1/jobs/{quote(normalized_job_id, safe='')}",
                token=_configured_token(self._control_token),
                expected_status=200,
                json={"status": "canceled", "lastError": "CONTROL_CANCELED"},
                parse_cancel_conflict=True,
            )
        except ProductCollectionGatewayError as error:
            if (
                error.failure_code == "PRODUCT_COLLECTION_GATEWAY_STATE_CONFLICT"
                and error.gateway_job_status in {"failed", "canceled"}
            ):
                return GatewayCancelResult(
                    gateway_job_id=normalized_job_id,
                    status=error.gateway_job_status,
                )
            raise
        try:
            envelope = _GatewayCancelEnvelope.model_validate(payload)
        except ValidationError:
            raise _invalid_response() from None
        if envelope.job.job_id != normalized_job_id:
            raise _invalid_response()
        return GatewayCancelResult(
            gateway_job_id=normalized_job_id,
            status="canceled",
        )

    def settle(self, settlement: GatewaySettlementV1) -> None:
        payload = self._request_json(
            "POST",
            SETTLEMENT_PATH,
            token=_configured_token(self._callback_token),
            expected_status=200,
            json=settlement.model_dump(mode="json", by_alias=True),
            settlement=True,
        )
        try:
            envelope = _GatewaySettlementEnvelope.model_validate(payload)
        except ValidationError:
            raise _invalid_response() from None
        if (
            envelope.settlement.gateway_job_id != settlement.job_id
            or envelope.settlement.capture_batch_id != settlement.capture_batch_id
        ):
            raise _invalid_response()

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        token: str,
        expected_status: int,
        json: dict[str, Any],
        settlement: bool = False,
        parse_cancel_conflict: bool = False,
    ) -> dict[str, Any]:
        try:
            with self._client_scope() as client:
                response = client.request(
                    method,
                    f"{self._base_url}{path}",
                    headers={"Authorization": f"Bearer {token}"},
                    json=json,
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                )
        except httpx.TimeoutException:
            raise ProductCollectionGatewayError(
                "PRODUCT_COLLECTION_GATEWAY_TIMEOUT",
                "手机采集网关请求超时",
                retryable=True,
            ) from None
        except httpx.RequestError:
            raise ProductCollectionGatewayError(
                "PRODUCT_COLLECTION_GATEWAY_UNAVAILABLE",
                "手机采集网关暂不可用",
                retryable=True,
            ) from None

        if response.status_code != expected_status:
            terminal_status = (
                _cancel_conflict_status(response)
                if parse_cancel_conflict and response.status_code == 409
                else None
            )
            raise _status_error(
                response.status_code,
                settlement=settlement,
                gateway_job_status=terminal_status,
            )
        try:
            payload = response.json()
        except ValueError:
            raise _invalid_response() from None
        if not isinstance(payload, dict):
            raise _invalid_response()
        return payload

    @contextmanager
    def _client_scope(self) -> Iterator[httpx.Client]:
        if self._client is not None:
            yield self._client
            return
        with httpx.Client(
            timeout=self._timeout_seconds,
            follow_redirects=False,
        ) as client:
            yield client


def _status_error(
    status_code: int,
    *,
    settlement: bool,
    gateway_job_status: Literal["failed", "canceled"] | None = None,
) -> ProductCollectionGatewayError:
    if status_code in {401, 403}:
        return ProductCollectionGatewayError(
            "PRODUCT_COLLECTION_GATEWAY_AUTHENTICATION_FAILED",
            "手机采集网关服务认证失败",
            retryable=False,
        )
    if status_code == 429:
        return ProductCollectionGatewayError(
            "PRODUCT_COLLECTION_GATEWAY_RATE_LIMITED",
            "手机采集网关请求过于频繁",
            retryable=True,
        )
    if status_code in {408, 425} or status_code >= 500:
        return ProductCollectionGatewayError(
            "PRODUCT_COLLECTION_GATEWAY_UNAVAILABLE",
            "手机采集网关暂不可用",
            retryable=True,
        )
    if status_code == 409:
        return ProductCollectionGatewayError(
            (
                "PRODUCT_COLLECTION_GATEWAY_SETTLEMENT_REJECTED"
                if settlement
                else "PRODUCT_COLLECTION_GATEWAY_STATE_CONFLICT"
            ),
            (
                "手机采集网关拒绝了终态结算"
                if settlement
                else "手机采集网关任务状态已变化"
            ),
            retryable=False,
            gateway_job_status=gateway_job_status,
        )
    return ProductCollectionGatewayError(
        (
            "PRODUCT_COLLECTION_GATEWAY_SETTLEMENT_REJECTED"
            if settlement
            else "PRODUCT_COLLECTION_GATEWAY_REQUEST_REJECTED"
        ),
        (
            "手机采集网关拒绝了终态结算"
            if settlement
            else "手机采集网关拒绝了请求"
        ),
        retryable=False,
    )


def _invalid_response() -> ProductCollectionGatewayError:
    return ProductCollectionGatewayError(
        "PRODUCT_COLLECTION_GATEWAY_RESPONSE_INVALID",
        "手机采集网关返回了无效响应",
        retryable=False,
    )


def _cancel_conflict_status(
    response: httpx.Response,
) -> Literal["failed", "canceled"] | None:
    """Read only the gateway's exact, documented terminal-conflict message."""

    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("ok") is not False:
        return None
    message = payload.get("error")
    if not isinstance(message, str):
        return None
    matched = _TERMINAL_CANCEL_CONFLICT.fullmatch(message)
    if matched is None:
        return None
    status = matched.group(1)
    return status if status in {"failed", "canceled"} else None


def _validated_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Gateway base URL is invalid")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError("Gateway base URL is invalid") from error
    return normalized


def _required(value: str, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{label} is required")
    return normalized


def _optional_secret(value: SecretStr | None, label: str) -> str | None:
    return None if value is None else _required(value.get_secret_value(), label)


def _configured_token(value: str | None) -> str:
    if value is None:
        raise ProductCollectionGatewayError(
            "PRODUCT_COLLECTION_GATEWAY_CONFIGURATION_UNAVAILABLE",
            "手机采集网关服务凭据尚未配置",
            retryable=False,
        )
    return value
