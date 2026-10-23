"""PostgreSQL persistence primitives for mobile product collection.

The repository owns row locks, claims and compare-and-set fences only.  It
does not perform authorization, external HTTP or package cleaning.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.orm import Session

from app.modules.product_collection.contracts import (
    GatewaySettlementV1,
    SourcePlatform,
    canonical_sha256,
)
from app.modules.product_collection.exceptions import ProductCollectionLeaseLostError
from app.modules.product_collection.models import (
    ProductCollectionCaptureAttempt as CaptureAttempt,
    ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item,
    ProductCollectionPersistReceipt as PersistReceipt,
    ProductCollectionRequest as CollectionRequest,
    ProductCollectionUploadReceipt as UploadReceipt,
    ProductLibraryProduct as Product,
    ProductLibraryProductVersion as ProductVersion,
)
from app.modules.product_collection.ports import (
    GatewaySettlementClaim,
    UploadProcessingClaim,
)
from app.shared.identifiers import generate_id


class ProductCollectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def now(self) -> datetime:
        return self.session.scalar(select(func.clock_timestamp()))

    def claim_upload(self, *, lease_seconds: int) -> UploadProcessingClaim | None:
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("Upload processing lease must be a positive integer")
        now = self.now()
        row = self.session.scalar(
            select(UploadReceipt)
            .where(
                or_(
                    and_(
                        UploadReceipt.state == "received",
                        or_(
                            UploadReceipt.processing_next_attempt_at.is_(None),
                            UploadReceipt.processing_next_attempt_at <= now,
                        ),
                    ),
                    and_(
                        UploadReceipt.state == "processing",
                        UploadReceipt.lease_expires_at <= now,
                    ),
                ),
            )
            .order_by(
                case((UploadReceipt.state == "processing", 0), else_=1),
                UploadReceipt.received_at,
                UploadReceipt.upload_receipt_id,
            )
            .with_for_update(skip_locked=True)
            .limit(1),
        )
        if row is None:
            return None

        lease_id = generate_id()
        row.state = "processing"
        row.processing_attempts += 1
        row.processing_next_attempt_at = None
        row.lease_id = lease_id
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        row.last_heartbeat_at = now
        row.last_error_code = None
        row.last_error_stage = None
        row.last_error_message = None

        attempt = self.lock_attempt(row.attempt_id, row.team_id)
        if attempt is None:
            raise ProductCollectionLeaseLostError()
        if attempt.state in {"received", "processing"}:
            attempt.state = "processing"
            attempt.last_heartbeat_at = now

        dispatch = self.lock_dispatch(attempt.dispatch_id, row.team_id)
        if dispatch is None:
            raise ProductCollectionLeaseLostError()
        item = self.lock_item(dispatch.item_id, row.team_id)
        if (
            item is not None
            and item.current_dispatch_id == dispatch.dispatch_id
            and item.state in {"received", "processing"}
        ):
            item.state = "processing"
        self.session.flush()
        return UploadProcessingClaim(row.upload_receipt_id, lease_id)

    def fence_upload(
        self,
        claim: UploadProcessingClaim,
    ) -> UploadReceipt:
        row = self.session.scalar(
            select(UploadReceipt)
            .where(
                UploadReceipt.upload_receipt_id == claim.upload_receipt_id,
                UploadReceipt.lease_id == claim.lease_id,
                UploadReceipt.state == "processing",
                UploadReceipt.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
            .execution_options(populate_existing=True),
        )
        database_now = self.now()
        if (
            row is None
            or row.lease_expires_at is None
            or row.lease_expires_at <= database_now
        ):
            raise ProductCollectionLeaseLostError()
        return row

    def heartbeat_upload(
        self,
        claim: UploadProcessingClaim,
        *,
        lease_seconds: int,
    ) -> bool:
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("Upload processing lease must be a positive integer")
        row = self.fence_upload(claim)
        now = self.now()
        row.last_heartbeat_at = now
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        return True

    def lock_attempt(self, attempt_id: UUID, team_id: UUID) -> CaptureAttempt | None:
        return self.session.scalar(
            select(CaptureAttempt)
            .where(
                CaptureAttempt.attempt_id == attempt_id,
                CaptureAttempt.team_id == team_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True),
        )

    def lock_dispatch(self, dispatch_id: UUID, team_id: UUID) -> Dispatch | None:
        return self.session.scalar(
            select(Dispatch)
            .where(Dispatch.dispatch_id == dispatch_id, Dispatch.team_id == team_id)
            .with_for_update()
            .execution_options(populate_existing=True),
        )

    def lock_item(self, item_id: UUID, team_id: UUID) -> Item | None:
        return self.session.scalar(
            select(Item)
            .where(Item.item_id == item_id, Item.team_id == team_id)
            .with_for_update()
            .execution_options(populate_existing=True),
        )

    def lock_request(self, request_id: UUID, team_id: UUID) -> CollectionRequest | None:
        return self.session.scalar(
            select(CollectionRequest)
            .where(
                CollectionRequest.request_id == request_id,
                CollectionRequest.team_id == team_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True),
        )

    def lock_product(
        self,
        *,
        team_id: UUID,
        platform: str,
        source_product_id: str,
    ) -> Product | None:
        return self.session.scalar(
            select(Product)
            .where(
                Product.team_id == team_id,
                Product.platform == platform,
                Product.source_product_id == source_product_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True),
        )

    def refresh_request_state(
        self,
        *,
        request_id: UUID,
        team_id: UUID,
        at: datetime,
    ) -> CollectionRequest:
        request = self.lock_request(request_id, team_id)
        if request is None:
            raise ProductCollectionLeaseLostError()
        states = tuple(
            self.session.scalars(
                select(Item.state)
                .where(Item.request_id == request_id, Item.team_id == team_id)
                .order_by(Item.item_id),
            ),
        )
        if not states or len(states) != request.item_count:
            raise ProductCollectionLeaseLostError()
        terminal = {"succeeded", "failed", "canceled"}
        if any(state not in terminal for state in states):
            request.status = "running"
            request.finished_at = None
        elif all(state == "succeeded" for state in states):
            request.status = "succeeded"
            request.finished_at = at
        elif all(state == "canceled" for state in states):
            request.status = "canceled"
            request.finished_at = at
        elif any(state == "succeeded" for state in states):
            request.status = "partial"
            request.finished_at = at
        else:
            request.status = "failed"
            request.finished_at = at
        return request

    def claim_settlement(
        self,
        *,
        max_attempts: int,
        delivery_timeout_seconds: int,
    ) -> GatewaySettlementClaim | None:
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("Settlement attempt budget must be positive")
        if type(delivery_timeout_seconds) is not int or delivery_timeout_seconds < 1:
            raise ValueError("Settlement delivery timeout must be positive")
        now = self.now()
        stale_before = now - timedelta(seconds=delivery_timeout_seconds)

        # A process can die after committing the final allowed claim.  Recover
        # that stale delivery to an explicit exhausted failure rather than
        # leaving an unclaimable `delivering` row forever.
        self.session.execute(
            update(UploadReceipt)
            .where(
                UploadReceipt.gateway_settlement_state == "delivering",
                UploadReceipt.updated_at <= stale_before,
                UploadReceipt.gateway_settlement_attempts >= max_attempts,
            )
            .values(
                gateway_settlement_state="failed",
                next_attempt_at=None,
                settlement_error_code="PRODUCT_COLLECTION_GATEWAY_SETTLEMENT_INTERRUPTED",
                settlement_error_message="结算进程中断且已达到重试上限",
                updated_at=now,
            ),
        )

        row = self.session.scalar(
            select(UploadReceipt)
            .where(
                UploadReceipt.state.in_(("persisted", "failed", "superseded")),
                UploadReceipt.gateway_settlement_attempts < max_attempts,
                or_(
                    UploadReceipt.gateway_settlement_state == "pending",
                    and_(
                        UploadReceipt.gateway_settlement_state == "failed",
                        UploadReceipt.next_attempt_at.is_not(None),
                        UploadReceipt.next_attempt_at <= now,
                    ),
                    and_(
                        UploadReceipt.gateway_settlement_state == "delivering",
                        UploadReceipt.updated_at <= stale_before,
                    ),
                ),
            )
            .order_by(
                case(
                    (UploadReceipt.gateway_settlement_state == "delivering", 0),
                    (UploadReceipt.gateway_settlement_state == "failed", 1),
                    else_=2,
                ),
                UploadReceipt.processed_at,
                UploadReceipt.upload_receipt_id,
            )
            .with_for_update(skip_locked=True)
            .limit(1),
        )
        if row is None:
            return None

        row.gateway_settlement_state = "delivering"
        row.gateway_settlement_attempts += 1
        row.next_attempt_at = None
        row.settlement_error_code = None
        row.settlement_error_message = None
        row.updated_at = now
        self.session.flush()
        return GatewaySettlementClaim(
            upload_receipt_id=row.upload_receipt_id,
            attempt_no=row.gateway_settlement_attempts,
            settlement=self._settlement_payload(row),
        )

    def _settlement_payload(self, upload: UploadReceipt) -> GatewaySettlementV1:
        attempt = self.session.get(CaptureAttempt, upload.attempt_id)
        if attempt is None or attempt.team_id != upload.team_id:
            raise ProductCollectionLeaseLostError()
        dispatch = self.session.get(Dispatch, attempt.dispatch_id)
        if dispatch is None or dispatch.team_id != upload.team_id:
            raise ProductCollectionLeaseLostError()
        item = self.session.get(Item, dispatch.item_id)
        if item is None or item.team_id != upload.team_id:
            raise ProductCollectionLeaseLostError()

        status = {
            "persisted": "succeeded",
            "failed": "failed",
            "superseded": "superseded",
        }[upload.state]
        if upload.processed_at is None:
            raise ProductCollectionLeaseLostError()
        product_version_id = None
        uu_sha256 = None
        error_code = None
        if status == "succeeded":
            receipt = self.session.scalar(
                select(PersistReceipt).where(
                    PersistReceipt.upload_receipt_id == upload.upload_receipt_id,
                    PersistReceipt.team_id == upload.team_id,
                ),
            )
            if receipt is None:
                raise ProductCollectionLeaseLostError()
            version = self.session.get(ProductVersion, receipt.version_id)
            if version is None or version.team_id != upload.team_id:
                raise ProductCollectionLeaseLostError()
            product_version_id = version.version_id
            uu_sha256 = canonical_sha256(version.uu_snapshot)
        else:
            error_code = upload.last_error_code or (
                "PRODUCT_COLLECTION_CAPTURE_SUPERSEDED"
                if status == "superseded"
                else "PRODUCT_COLLECTION_PROCESSING_FAILED"
            )
        return GatewaySettlementV1(
            schemaVersion=1,
            dispatchId=dispatch.dispatch_id,
            gatewayId=dispatch.gateway_id,
            externalJobId=dispatch.external_job_id,
            gatewayJobId=attempt.gateway_job_id,
            captureBatchId=attempt.capture_batch_id,
            deviceId=attempt.gateway_device_id,
            sourcePlatform=SourcePlatform(item.platform),
            sourceProductId=item.source_product_id,
            attemptId=attempt.attempt_id,
            receiptId=upload.upload_receipt_id,
            status=status,
            errorCode=error_code,
            errorMessage=(upload.last_error_message if status != "succeeded" else None),
            productVersionId=product_version_id,
            uuSha256=uu_sha256,
            persistedAt=upload.processed_at,
        )

    def fence_settlement(
        self,
        claim: GatewaySettlementClaim,
    ) -> tuple[UploadReceipt, CaptureAttempt]:
        upload = self.session.scalar(
            select(UploadReceipt)
            .where(
                UploadReceipt.upload_receipt_id == claim.upload_receipt_id,
                UploadReceipt.gateway_settlement_state == "delivering",
                UploadReceipt.gateway_settlement_attempts == claim.attempt_no,
            )
            .with_for_update()
            .execution_options(populate_existing=True),
        )
        if upload is None:
            raise ProductCollectionLeaseLostError()
        attempt = self.lock_attempt(upload.attempt_id, upload.team_id)
        if attempt is None:
            raise ProductCollectionLeaseLostError()
        return upload, attempt
