"""Narrow external ports for the existing mobile gateway and UU cleaner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol
from uuid import UUID

from app.modules.product_collection.contracts import GatewaySettlementV1, SourcePlatform


# Normal default and upper bound; 1..3 is frozen in each Dispatch's hash.
GATEWAY_CAPTURE_MAX_ATTEMPTS = 3


@dataclass(frozen=True, slots=True)
class GatewayDispatchCommand:
    """One idempotent central-to-gateway delivery, never a phone claim."""

    dispatch_id: UUID
    external_job_id: str
    canonical_payload_hash: str
    source_platform: SourcePlatform
    source_product_id: str
    ingest_mode: str = "central_ingest_v1"
    job_type: str = "product"
    recapture: bool = False
    priority: int = 0
    max_attempts: int = GATEWAY_CAPTURE_MAX_ATTEMPTS

    def payload(self) -> dict[str, Any]:
        return {
            "schemaVersion": 1,
            "dispatchId": str(self.dispatch_id),
            "externalJobId": self.external_job_id,
            "canonicalPayloadHash": self.canonical_payload_hash,
            "sourcePlatform": self.source_platform.value,
            "sourceProductId": self.source_product_id,
            "ingestMode": self.ingest_mode,
            "jobType": self.job_type,
            "recapture": self.recapture,
            "priority": self.priority,
            "maxAttempts": self.max_attempts,
        }


@dataclass(frozen=True, slots=True)
class GatewayDispatchResult:
    gateway_id: str
    gateway_job_id: str
    external_job_id: str
    status: str
    reused: bool


@dataclass(frozen=True, slots=True)
class GatewayCancelResult:
    """Authoritative terminal state returned by one gateway cancel attempt."""

    gateway_job_id: str
    status: Literal["failed", "canceled"]


@dataclass(frozen=True, slots=True)
class GatewayJobState:
    """Allowlisted job status; error_message is safe adapter-owned text."""

    gateway_id: str
    gateway_job_id: str
    external_job_id: str
    source_platform: str
    source_product_id: str
    capture_batch_id: str | None
    status: str
    attempts: int
    max_attempts: int
    error_message: str = "手机采集网关任务已失败"


class ProductCollectionGateway(Protocol):
    """Service-authenticated operations exposed by the existing gateway."""

    def deliver(self, command: GatewayDispatchCommand) -> GatewayDispatchResult: ...

    def retry(self, *, gateway_job_id: str) -> GatewayDispatchResult: ...

    def cancel(self, *, gateway_job_id: str) -> GatewayCancelResult: ...

    def status(self, *, gateway_job_id: str, external_job_id: str) -> GatewayJobState: ...

    def settle(self, settlement: GatewaySettlementV1) -> None: ...


@dataclass(frozen=True, slots=True)
class CleanedProductPackage:
    """Versioned output of the reviewed convertCompletePackage adapter."""

    source_platform: SourcePlatform
    source_product_id: str
    captured_at: datetime
    source_format_version: int
    cleaner_version: str
    title: str | None
    source_url: str | None
    primary_image_url: str | None
    merchant_snapshot: dict[str, Any] | None
    category_path: tuple[str, ...] | None
    current_sale_price_cent: int | None
    currency: str | None
    uu_snapshot: dict[str, Any]
    price_evidence: dict[str, Any]


class ProductPackageCleaner(Protocol):
    """No database or gateway access; the implementation only cleans one package."""

    def convert(self, raw_package: dict[str, Any]) -> CleanedProductPackage: ...


@dataclass(frozen=True, slots=True)
class DeliveryClaim:
    dispatch_id: UUID
    lease_id: UUID
    command: GatewayDispatchCommand
    retry_gateway_job_id: str | None
    attempt_no: int


@dataclass(frozen=True, slots=True)
class GatewayStatusClaim:
    dispatch_id: UUID
    item_id: UUID
    team_id: UUID
    gateway_id: str
    gateway_job_id: str
    external_job_id: str
    source_platform: str
    source_product_id: str
    attempt_id: UUID | None
    capture_batch_id: str | None
    gateway_device_id: str | None


@dataclass(frozen=True, slots=True)
class UploadProcessingClaim:
    upload_receipt_id: UUID
    lease_id: UUID


@dataclass(frozen=True, slots=True)
class GatewaySettlementClaim:
    """One fenced outbox delivery attempt.

    ``attempt_no`` is the durable compare-and-set fence.  The gateway
    operation itself stays outside the database transaction and is expected
    to be idempotent for the job/batch tuple carried by ``settlement``.
    """

    upload_receipt_id: UUID
    attempt_no: int
    settlement: GatewaySettlementV1
