"""Versioned contracts for central-to-gateway mobile product collection."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
from typing import Annotated, Any, Literal
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.product_collection.media_urls import collector_v2_media_query_keys


StableExternalId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
Sha256Hex = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class SourcePlatform(StrEnum):
    DOUYIN = "douyin"
    PINDUODUO = "pinduoduo"


class CollectionSourceKind(StrEnum):
    MANUAL = "manual"
    SELECTION_CANDIDATES = "selection_candidates"


class ManualCollectionTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    platform: SourcePlatform
    product_id_or_supported_url: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=4096),
    ]


class ManualCollectionSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[CollectionSourceKind.MANUAL]
    targets: tuple[ManualCollectionTarget, ...] = Field(min_length=1, max_length=100)


class CandidateCollectionSource(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal[CollectionSourceKind.SELECTION_CANDIDATES]
    candidate_ids: tuple[UUID, ...] = Field(min_length=1, max_length=100)


CollectionSource = Annotated[
    ManualCollectionSource | CandidateCollectionSource,
    Field(discriminator="kind"),
]


class ProductCollectionRequestCreate(BaseModel):
    """Human request; Team ownership always comes from ActorContext."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    submission_key: UUID
    target_group_id: UUID | None = None
    source: CollectionSource

    def canonical_hash(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))


class MobileTaskContextV1(BaseModel):
    """Non-secret identity copied into one phone complete package."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    job_id: StableExternalId = Field(alias="jobId")
    capture_batch_id: StableExternalId = Field(alias="captureBatchId")
    job_type: Annotated[str, StringConstraints(min_length=1, max_length=64)] = Field(alias="jobType")
    source_platform: SourcePlatform = Field(alias="sourcePlatform")
    source_product_id: StableExternalId = Field(alias="sourceProductId")
    recapture_requested: bool = Field(default=False, alias="recaptureRequested")


class MobileCompletePackageV1(BaseModel):
    """Strict top-level allowlist accepted before invoking the existing cleaner."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    event_type: Literal["complete"] = Field(alias="eventType")
    detail_body: dict[str, Any] = Field(alias="detailBody")
    sku_body: dict[str, Any] = Field(alias="skuBody")
    captured_at: int = Field(alias="capturedAt", ge=0)
    sku_captured_at: int | None = Field(default=None, alias="skuCapturedAt", ge=0)
    task_context: MobileTaskContextV1 = Field(alias="taskContext")

    @field_validator("detail_body", "sku_body")
    @classmethod
    def reject_credential_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        assert_no_credential_keys(value)
        return value


class MobileCompletePackageV2(BaseModel):
    """Exact allowlist emitted by the existing Douyin collector package writer."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_version: Literal[2] = Field(alias="schemaVersion")
    source: Literal[SourcePlatform.DOUYIN]
    event_type: Literal["complete"] = Field(alias="eventType")
    trigger: Literal["cart_sku", "detail_single_sku"]
    product_id: StableExternalId = Field(alias="productId")
    captured_at: int = Field(alias="capturedAt", ge=0, strict=True)
    detail_captured_at: int = Field(alias="detailCapturedAt", ge=0, strict=True)
    sku_captured_at: int = Field(alias="skuCapturedAt", ge=0, strict=True)
    app_version: Annotated[str, StringConstraints(min_length=1, max_length=128)] = Field(
        alias="appVersion",
    )
    detail_sha256: Sha256Hex = Field(alias="detailSha256")
    sku_sha256: Sha256Hex = Field(alias="skuSha256")
    sha256: Sha256Hex
    detail_body: dict[str, Any] = Field(alias="detailBody")
    sku_body: dict[str, Any] = Field(alias="skuBody")
    task_context: MobileTaskContextV1 = Field(alias="taskContext")

    @field_validator("detail_body")
    @classmethod
    def reject_credential_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        assert_no_credential_keys(value, collector_v2_media=True)
        return value

    @field_validator("sku_body")
    @classmethod
    def reject_sku_credential_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        assert_no_credential_keys(value)
        return value

    @model_validator(mode="after")
    def require_matching_top_level_identity(self):
        if (
            self.source != self.task_context.source_platform
            or self.product_id != self.task_context.source_product_id
        ):
            raise ValueError("Complete package identity does not match taskContext")
        return self


MobileCompletePackage = MobileCompletePackageV1 | MobileCompletePackageV2


class GatewayAttemptRegistrationV1(BaseModel):
    """Trusted gateway service registration after its claim transaction commits."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_version: Literal[1] = Field(alias="schemaVersion")
    dispatch_id: UUID = Field(alias="dispatchId")
    gateway_id: StableExternalId = Field(alias="gatewayId")
    external_job_id: StableExternalId = Field(alias="externalJobId")
    gateway_job_id: StableExternalId = Field(alias="gatewayJobId")
    device_id: StableExternalId = Field(alias="deviceId")
    capture_batch_id: StableExternalId = Field(alias="captureBatchId")
    source_platform: Literal[SourcePlatform.DOUYIN] = Field(alias="sourcePlatform")
    source_product_id: StableExternalId = Field(alias="sourceProductId")
    lease_expires_at: datetime = Field(alias="leaseExpiresAt")

    @field_validator("lease_expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Lease expiry must include a timezone")
        return value


class ControlIngestV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    protocol: Literal["central_ingest_v1"]
    attempt_id: UUID = Field(alias="attemptId")
    upload_url: Annotated[str, StringConstraints(pattern=r"^https?://", max_length=4096)] = Field(
        alias="uploadUrl",
    )
    credential: Annotated[str, StringConstraints(min_length=43, max_length=256)] = Field(repr=False)
    credential_id: UUID = Field(alias="credentialId")
    expires_at: datetime = Field(alias="expiresAt")


class GatewayAttemptRegistrationResponseV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    ok: Literal[True] = True
    control_ingest: ControlIngestV1 = Field(alias="controlIngest")


class GatewayCredentialRefreshV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_version: Literal[1] = Field(alias="schemaVersion")
    gateway_id: StableExternalId = Field(alias="gatewayId")
    gateway_job_id: StableExternalId = Field(alias="gatewayJobId")
    device_id: StableExternalId = Field(alias="deviceId")
    capture_batch_id: StableExternalId = Field(alias="captureBatchId")
    credential_id: UUID = Field(alias="credentialId")


class UploadReceiptV1(BaseModel):
    """Durable raw-package acknowledgement, not a persistence receipt."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    accepted: Literal[True] = True
    status: Literal["received", "duplicate", "superseded"]
    receipt_id: UUID = Field(alias="receiptId")
    attempt_id: UUID = Field(alias="attemptId")
    capture_batch_id: StableExternalId = Field(alias="captureBatchId")
    received_at: datetime = Field(alias="receivedAt")


class UploadAcceptedV1(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    ok: Literal[True] = True
    receipt: UploadReceiptV1


class GatewaySettlementV1(BaseModel):
    """Persisted outcome sent to the gateway; received-only never settles success."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    dispatch_id: UUID = Field(alias="dispatchId")
    gateway_id: StableExternalId = Field(alias="gatewayId")
    external_job_id: StableExternalId = Field(alias="externalJobId")
    job_id: StableExternalId = Field(alias="gatewayJobId")
    capture_batch_id: StableExternalId = Field(alias="captureBatchId")
    device_id: StableExternalId = Field(alias="deviceId")
    source_platform: SourcePlatform = Field(alias="sourcePlatform")
    source_product_id: StableExternalId = Field(alias="sourceProductId")
    attempt_id: UUID = Field(alias="attemptId")
    receipt_id: UUID = Field(alias="receiptId")
    status: Literal["succeeded", "failed", "canceled", "superseded"]
    error_code: Annotated[str, StringConstraints(max_length=96)] | None = Field(
        default=None,
        alias="errorCode",
    )
    error_message: Annotated[str, StringConstraints(max_length=500)] | None = Field(
        default=None,
        alias="errorMessage",
    )
    product_version_id: UUID | None = Field(default=None, alias="productVersionId")
    uu_sha256: Sha256Hex | None = Field(default=None, alias="uuSha256")
    persisted_at: datetime = Field(alias="persistedAt")

    @field_validator("persisted_at")
    @classmethod
    def require_persisted_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Settlement timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_outcome(self) -> GatewaySettlementV1:
        success = self.status == "succeeded"
        has_product_result = (
            self.product_version_id is not None and self.uu_sha256 is not None
        )
        if success != has_product_result:
            raise ValueError("Successful settlement requires product version and UU hash")
        if not success and (
            self.product_version_id is not None or self.uu_sha256 is not None
        ):
            raise ValueError("Non-success settlement cannot include a product result")
        if success and (self.error_code is not None or self.error_message is not None):
            raise ValueError("Successful settlement cannot include an error")
        if not success and self.error_code is None:
            raise ValueError("Non-success settlement requires a stable error code")
        return self


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


_CREDENTIAL_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "cookies",
        "token",
        "access_token",
        "refresh_token",
        "signature",
        "a_bogus",
        "ms_token",
        "mstoken",
        "headers",
        "request_headers",
        "response_headers",
        "request_url",
        "request_uri",
    },
)

_CREDENTIAL_QUERY_KEYS = frozenset(
    {
        "auth",
        "auth_key",
        "expires",
        "expiry",
        "sig",
        "sign",
        "x_signature",
    },
)


def _looks_like_credential_key(value: str) -> bool:
    normalized = value.strip().lower().replace("-", "_")
    return (
        normalized in _CREDENTIAL_KEYS
        or normalized in _CREDENTIAL_QUERY_KEYS
        or normalized.endswith("_token")
        or normalized.endswith("_signature")
    )


def assert_no_credential_keys(
    value: Any, *, collector_v2_media: bool = False, _path: tuple[str | None, ...] = (),
) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if _looks_like_credential_key(normalized):
                raise ValueError("Complete package contains a forbidden credential field")
            assert_no_credential_keys(
                nested, collector_v2_media=collector_v2_media, _path=(*_path, str(key)),
            )
    elif isinstance(value, list):
        for nested in value:
            assert_no_credential_keys(
                nested, collector_v2_media=collector_v2_media, _path=(*_path, None),
            )
    elif isinstance(value, str):
        candidate = value.strip()
        media_keys = (
            collector_v2_media_query_keys(_path, candidate)
            if collector_v2_media and "://" in candidate else frozenset()
        )
        if not candidate.lower().startswith(("http://", "https://")):
            return
        if len(candidate) > 4096:
            raise ValueError("Complete package contains an oversized URL")
        parsed = urlsplit(candidate)
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Complete package contains a credential-bearing URL")
        if any(
            _looks_like_credential_key(key) and key.strip().lower().replace("-", "_") not in media_keys
            for key, _item in parse_qsl(parsed.query, keep_blank_values=True)
        ):
            raise ValueError("Complete package contains a credential-bearing URL")
