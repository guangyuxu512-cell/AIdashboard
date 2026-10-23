"""Short-transaction processing and settlement services.

External package cleaning and gateway HTTP calls must happen between these
methods, never while a database transaction is held open.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.product_collection.exceptions import ProductCollectionLeaseLostError
from app.modules.product_collection.models import (
    ProductCollectionCaptureAttempt as CaptureAttempt,
    ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item,
    ProductCollectionPersistReceipt as PersistReceipt,
    ProductCollectionUploadReceipt as UploadReceipt,
    ProductLibraryProduct as Product,
    ProductLibraryProductVersion as ProductVersion,
)
from app.modules.product_collection.ports import (
    CleanedProductPackage,
    GatewaySettlementClaim,
    UploadProcessingClaim,
)
from app.modules.product_collection.repository import ProductCollectionRepository
from app.shared.identifiers import generate_id


@dataclass(frozen=True, slots=True)
class PersistedPackageResult:
    upload_receipt_id: UUID
    persist_receipt_id: UUID
    product_id: UUID
    version_id: UUID
    outcome: str
    applied: bool


class ProductCollectionProcessingService:
    """Owns Inbox processing and the Upload→Version/Persist invariant."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ProductCollectionRepository(session)

    def claim(self, *, lease_seconds: int) -> UploadProcessingClaim | None:
        try:
            claim = self.repository.claim_upload(lease_seconds=lease_seconds)
            self.session.commit()
            return claim
        except Exception:
            self.session.rollback()
            raise

    def raw_payload(self, claim: UploadProcessingClaim) -> dict:
        row = self.repository.fence_upload(claim)
        payload = dict(row.raw_payload)
        self.session.rollback()
        return payload

    def heartbeat(self, claim: UploadProcessingClaim, *, lease_seconds: int) -> bool:
        try:
            changed = self.repository.heartbeat_upload(claim, lease_seconds=lease_seconds)
            self.session.commit()
            return changed
        except Exception:
            self.session.rollback()
            raise

    def persist(
        self,
        claim: UploadProcessingClaim,
        package: CleanedProductPackage,
        *,
        at: datetime | None = None,
    ) -> PersistedPackageResult:
        if package.captured_at.tzinfo is None or package.captured_at.utcoffset() is None:
            raise ValueError("Package captured_at must include a timezone")
        try:
            actual_at = _aware(at) if at is not None else self.repository.now()
            upload, attempt, dispatch, item = self._processing_chain(claim)
            if (
                package.source_platform.value != item.platform
                or package.source_product_id != item.source_product_id
            ):
                raise ValueError("Cleaned package identity does not match its bound item")
            if item.current_dispatch_id != dispatch.dispatch_id:
                self._supersede_stale_upload(
                    upload=upload,
                    attempt=attempt,
                    at=actual_at,
                )
                self.session.commit()
                raise ProductCollectionLeaseLostError()

            product = self.repository.lock_product(
                team_id=item.team_id,
                platform=item.platform,
                source_product_id=item.source_product_id,
            )
            if product is None:
                request = self.repository.lock_request(item.request_id, item.team_id)
                if request is None:
                    raise ProductCollectionLeaseLostError()
                product = Product(
                    product_id=generate_id(),
                    team_id=item.team_id,
                    platform=item.platform,
                    source_product_id=item.source_product_id,
                    group_id=item.target_group_id,
                    manual_revision=0,
                    created_by_user_id=request.requested_by_user_id,
                )
                self.session.add(product)
                self.session.flush()

            version = ProductVersion(
                version_id=generate_id(),
                product_id=product.product_id,
                team_id=product.team_id,
                upload_receipt_id=upload.upload_receipt_id,
                captured_at=package.captured_at,
                source_format_version=package.source_format_version,
                cleaner_version=package.cleaner_version,
                raw_content_sha256=upload.content_sha256,
                uu_snapshot=package.uu_snapshot,
                price_evidence=package.price_evidence,
            )
            self.session.add(version)
            self.session.flush()

            revision_matches = (
                item.expected_manual_revision is None
                or item.expected_manual_revision == product.manual_revision
            )
            capture_is_current = (
                product.last_applied_capture_at is None
                or package.captured_at >= product.last_applied_capture_at
            )
            applied = revision_matches and capture_is_current
            outcome = "applied" if applied else (
                "not_applied" if not revision_matches else "superseded"
            )
            product.last_ingested_at = actual_at
            if applied:
                product.title = package.title
                product.source_url = package.source_url
                product.primary_image_url = package.primary_image_url
                product.merchant_snapshot = package.merchant_snapshot
                product.category_path = (
                    list(package.category_path) if package.category_path is not None else None
                )
                product.current_sale_price_cent = package.current_sale_price_cent
                product.currency = package.currency
                product.last_applied_capture_at = package.captured_at
                product.adopted_version_id = version.version_id

            persist_receipt = PersistReceipt(
                persist_receipt_id=generate_id(),
                team_id=item.team_id,
                upload_receipt_id=upload.upload_receipt_id,
                product_id=product.product_id,
                version_id=version.version_id,
                outcome=outcome,
                applied=applied,
                persisted_at=actual_at,
            )
            self.session.add(persist_receipt)

            upload.state = "persisted"
            upload.processed_at = actual_at
            upload.processing_next_attempt_at = None
            upload.lease_id = None
            upload.lease_expires_at = None
            upload.last_heartbeat_at = actual_at
            upload.last_error_code = None
            upload.last_error_stage = None
            upload.last_error_message = None
            upload.gateway_settlement_state = "pending"
            upload.next_attempt_at = None
            upload.settled_at = None
            upload.settlement_error_code = None
            upload.settlement_error_message = None

            attempt.state = "persisted"
            attempt.finished_at = actual_at
            attempt.last_heartbeat_at = actual_at
            attempt.last_error_code = None
            attempt.last_error_stage = None
            attempt.last_error_message = None

            dispatch.state = "completed"
            dispatch.finished_at = actual_at
            dispatch.lease_id = None
            dispatch.lease_expires_at = None
            dispatch.last_error_code = None
            dispatch.last_error_stage = None
            dispatch.last_error_message = None

            item.state = "succeeded"
            item.library_product_id = product.product_id
            item.finished_at = actual_at
            item.last_error_code = None
            item.last_error_stage = None
            item.last_error_message = None
            self.repository.refresh_request_state(
                request_id=item.request_id,
                team_id=item.team_id,
                at=actual_at,
            )
            self.session.commit()
            return PersistedPackageResult(
                upload.upload_receipt_id,
                persist_receipt.persist_receipt_id,
                product.product_id,
                version.version_id,
                outcome,
                applied,
            )
        except ProductCollectionLeaseLostError:
            # `_supersede_stale_upload` is a durable terminal receipt and must
            # survive the outward stale-claim signal.
            if self.session.in_transaction():
                self.session.rollback()
            raise
        except Exception:
            self.session.rollback()
            raise

    def fail(
        self,
        claim: UploadProcessingClaim,
        *,
        error_code: str,
        error_stage: str,
        error_message: str,
        at: datetime | None = None,
    ) -> None:
        safe_code, safe_stage, safe_message = _safe_error(
            error_code,
            error_stage,
            error_message,
        )
        try:
            actual_at = _aware(at) if at is not None else self.repository.now()
            upload, attempt, dispatch, item = self._processing_chain(claim)
            upload.state = "failed"
            upload.processed_at = actual_at
            upload.processing_next_attempt_at = None
            upload.lease_id = None
            upload.lease_expires_at = None
            upload.last_heartbeat_at = actual_at
            upload.last_error_code = safe_code
            upload.last_error_stage = safe_stage
            upload.last_error_message = safe_message
            upload.gateway_settlement_state = "pending"
            upload.next_attempt_at = None
            upload.settled_at = None
            upload.settlement_error_code = None
            upload.settlement_error_message = None

            attempt.state = "failed"
            attempt.finished_at = actual_at
            attempt.last_heartbeat_at = actual_at
            attempt.last_error_code = safe_code
            attempt.last_error_stage = safe_stage
            attempt.last_error_message = safe_message

            dispatch.state = "execution_failed"
            dispatch.finished_at = actual_at
            dispatch.lease_id = None
            dispatch.lease_expires_at = None
            dispatch.last_error_code = safe_code
            dispatch.last_error_stage = safe_stage
            dispatch.last_error_message = safe_message

            if item.current_dispatch_id == dispatch.dispatch_id:
                item.state = "failed"
                item.finished_at = actual_at
                item.last_error_code = safe_code
                item.last_error_stage = safe_stage
                item.last_error_message = safe_message
                self.repository.refresh_request_state(
                    request_id=item.request_id,
                    team_id=item.team_id,
                    at=actual_at,
                )
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def _processing_chain(
        self,
        claim: UploadProcessingClaim,
    ) -> tuple[UploadReceipt, CaptureAttempt, Dispatch, Item]:
        upload = self.repository.fence_upload(claim)
        attempt = self.repository.lock_attempt(upload.attempt_id, upload.team_id)
        if attempt is None or attempt.state != "processing":
            raise ProductCollectionLeaseLostError()
        dispatch = self.repository.lock_dispatch(attempt.dispatch_id, upload.team_id)
        if dispatch is None:
            raise ProductCollectionLeaseLostError()
        item = self.repository.lock_item(dispatch.item_id, upload.team_id)
        if item is None:
            raise ProductCollectionLeaseLostError()
        return upload, attempt, dispatch, item

    def _supersede_stale_upload(
        self,
        *,
        upload: UploadReceipt,
        attempt: CaptureAttempt,
        at: datetime,
    ) -> None:
        upload.state = "superseded"
        upload.processed_at = at
        upload.lease_id = None
        upload.lease_expires_at = None
        upload.last_error_code = "PRODUCT_COLLECTION_CAPTURE_SUPERSEDED"
        upload.last_error_stage = "capture_fence"
        upload.last_error_message = "采集批次已被新的派发替代"
        upload.gateway_settlement_state = "pending"
        upload.next_attempt_at = None
        attempt.state = "superseded"
        attempt.finished_at = at
        attempt.last_error_code = upload.last_error_code
        attempt.last_error_stage = upload.last_error_stage
        attempt.last_error_message = upload.last_error_message


class ProductCollectionSettlementService:
    """Durable finite-retry delivery of terminal outcomes to the gateway."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ProductCollectionRepository(session)

    def claim(
        self,
        *,
        max_attempts: int,
        delivery_timeout_seconds: int,
    ) -> GatewaySettlementClaim | None:
        try:
            claim = self.repository.claim_settlement(
                max_attempts=max_attempts,
                delivery_timeout_seconds=delivery_timeout_seconds,
            )
            self.session.commit()
            return claim
        except Exception:
            self.session.rollback()
            raise

    def succeed(
        self,
        claim: GatewaySettlementClaim,
        *,
        at: datetime | None = None,
    ) -> None:
        try:
            actual_at = _aware(at) if at is not None else self.repository.now()
            upload, attempt = self.repository.fence_settlement(claim)
            upload.gateway_settlement_state = "settled"
            upload.next_attempt_at = None
            upload.settled_at = actual_at
            upload.settlement_error_code = None
            upload.settlement_error_message = None
            attempt.settled_at = actual_at
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def fail(
        self,
        claim: GatewaySettlementClaim,
        *,
        error_code: str,
        error_message: str,
        max_attempts: int,
        retry_delay_seconds: int,
        at: datetime | None = None,
    ) -> bool:
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("Settlement attempt budget must be positive")
        if type(retry_delay_seconds) is not int or retry_delay_seconds < 0:
            raise ValueError("Settlement retry delay cannot be negative")
        safe_code, _, safe_message = _safe_error(
            error_code,
            "gateway_settlement",
            error_message,
        )
        try:
            actual_at = _aware(at) if at is not None else self.repository.now()
            upload, _ = self.repository.fence_settlement(claim)
            retryable = claim.attempt_no < max_attempts
            upload.gateway_settlement_state = "failed"
            upload.next_attempt_at = (
                actual_at + timedelta(seconds=retry_delay_seconds)
                if retryable
                else None
            )
            upload.settlement_error_code = safe_code
            upload.settlement_error_message = safe_message
            self.session.commit()
            return retryable
        except Exception:
            self.session.rollback()
            raise


def _aware(value: datetime | None) -> datetime:
    actual = value or datetime.now(UTC)
    if actual.tzinfo is None or actual.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return actual


def _safe_error(code: str, stage: str, message: str) -> tuple[str, str, str]:
    safe_code = code.strip()[:96]
    safe_stage = stage.strip()[:64]
    safe_message = " ".join(message.split())[:500]
    if not safe_code or not safe_stage:
        raise ValueError("Error code and stage must be non-blank")
    return safe_code, safe_stage, safe_message
