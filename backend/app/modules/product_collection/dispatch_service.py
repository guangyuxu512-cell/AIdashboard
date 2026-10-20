"""Reliable central-to-gateway dispatch without duplicating the phone queue."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.modules.product_collection.contracts import SourcePlatform, canonical_sha256
from app.modules.product_collection.exceptions import (
    ProductCollectionGatewayUnavailableError,
    ProductCollectionLeaseLostError,
)
from app.modules.product_collection.models import (
    ProductCollectionCaptureAttempt as CaptureAttempt,
    ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item,
    ProductCollectionRequest as CollectionRequest,
)
from app.modules.product_collection.ports import (
    DeliveryClaim,
    GatewayDispatchCommand,
    GatewayDispatchResult,
    ProductCollectionGateway,
)
from app.modules.product_collection.repository import ProductCollectionRepository
from app.shared.identifiers import generate_id


class ProductCollectionDispatchService:
    """Short DB claims around one external idempotent gateway operation."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ProductCollectionRepository(session)

    def plan_pending(self, *, gateway_id: str, limit: int = 100) -> int:
        normalized_gateway = gateway_id.strip()
        if not normalized_gateway or len(normalized_gateway) > 128:
            raise ValueError("Gateway id is invalid")
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Dispatch planning limit is invalid")
        try:
            items = list(
                self.session.scalars(
                    select(Item)
                    .where(
                        Item.state == "pending_dispatch",
                        Item.collection_mode == "auto_gateway",
                        Item.current_dispatch_id.is_(None),
                        ~exists_active_dispatch(Item.item_id),
                    )
                    .order_by(Item.created_at, Item.item_id)
                    .with_for_update(skip_locked=True)
                    .limit(limit),
                ),
            )
            for item in items:
                dispatch_id = generate_id()
                dispatch_no = (
                    self.session.scalar(
                        select(func.coalesce(func.max(Dispatch.dispatch_no), 0)).where(
                            Dispatch.item_id == item.item_id,
                        ),
                    )
                    + 1
                )
                command = build_dispatch_command(dispatch_id, item, recapture=False)
                dispatch = Dispatch(
                    dispatch_id=dispatch_id,
                    item_id=item.item_id,
                    team_id=item.team_id,
                    dispatch_no=dispatch_no,
                    external_job_id=command.external_job_id,
                    canonical_payload_hash=command.canonical_payload_hash,
                    gateway_id=normalized_gateway,
                    state="pending_delivery",
                    delivery_attempts=0,
                )
                self.session.add(dispatch)
                self.session.flush()
                item.current_dispatch_id = dispatch.dispatch_id
                item.state = "dispatching"
                request = self.repository.lock_request(item.request_id, item.team_id)
                if request is None:
                    raise ProductCollectionLeaseLostError()
                request.status = "running"
                request.finished_at = None
            self.session.commit()
            return len(items)
        except Exception:
            self.session.rollback()
            raise

    def claim(
        self,
        *,
        lease_seconds: int,
        max_attempts: int,
    ) -> DeliveryClaim | None:
        if type(lease_seconds) is not int or lease_seconds < 1:
            raise ValueError("Dispatch lease must be positive")
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("Dispatch attempt budget must be positive")
        try:
            now = self.repository.now()
            # A process can die after committing the last allowed delivery
            # claim.  Close that expired claim explicitly so it cannot remain
            # `delivering` forever with no remaining attempt budget.
            exhausted = self.session.scalar(
                select(Dispatch)
                .where(
                    Dispatch.state == "delivering",
                    Dispatch.lease_expires_at <= now,
                    Dispatch.delivery_attempts >= max_attempts,
                )
                .order_by(Dispatch.lease_expires_at, Dispatch.dispatch_id)
                .with_for_update(skip_locked=True)
                .limit(1),
            )
            if exhausted is not None:
                item = self.repository.lock_item(exhausted.item_id, exhausted.team_id)
                if (
                    item is None
                    or item.current_dispatch_id != exhausted.dispatch_id
                    or item.state not in {"dispatching", "failed"}
                ):
                    raise ProductCollectionLeaseLostError()
                exhausted.state = "delivery_failed"
                exhausted.next_attempt_at = None
                exhausted.lease_id = None
                exhausted.lease_expires_at = None
                exhausted.last_heartbeat_at = None
                exhausted.finished_at = now
                exhausted.last_error_code = (
                    "PRODUCT_COLLECTION_GATEWAY_DELIVERY_INTERRUPTED"
                )
                exhausted.last_error_stage = "gateway_delivery"
                exhausted.last_error_message = "网关投递进程中断且已达到重试上限"
                item.state = "failed"
                item.finished_at = now
                item.last_error_code = exhausted.last_error_code
                item.last_error_stage = exhausted.last_error_stage
                item.last_error_message = exhausted.last_error_message
                self.repository.refresh_request_state(
                    request_id=item.request_id,
                    team_id=item.team_id,
                    at=now,
                )

            dispatch = self.session.scalar(
                select(Dispatch)
                .where(
                    Dispatch.delivery_attempts < max_attempts,
                    or_(
                        and_(
                            Dispatch.state == "pending_delivery",
                            or_(
                                Dispatch.next_attempt_at.is_(None),
                                Dispatch.next_attempt_at <= now,
                            ),
                        ),
                        and_(
                            Dispatch.state == "delivering",
                            Dispatch.lease_expires_at <= now,
                        ),
                    ),
                )
                .order_by(
                    case((Dispatch.state == "delivering", 0), else_=1),
                    Dispatch.created_at,
                    Dispatch.dispatch_id,
                )
                .with_for_update(skip_locked=True)
                .limit(1),
            )
            if dispatch is None:
                if exhausted is not None:
                    self.session.commit()
                else:
                    self.session.rollback()
                return None
            item = self.repository.lock_item(dispatch.item_id, dispatch.team_id)
            if (
                item is None
                or item.current_dispatch_id != dispatch.dispatch_id
                or item.state not in {"dispatching", "failed"}
            ):
                raise ProductCollectionLeaseLostError()
            lease_id = generate_id()
            dispatch.state = "delivering"
            dispatch.delivery_attempts += 1
            dispatch.lease_id = lease_id
            dispatch.lease_expires_at = now + timedelta(seconds=lease_seconds)
            dispatch.last_heartbeat_at = now
            dispatch.next_attempt_at = None
            dispatch.finished_at = None
            item.state = "dispatching"
            item.finished_at = None
            self.session.commit()
            return DeliveryClaim(
                dispatch_id=dispatch.dispatch_id,
                lease_id=lease_id,
                command=command_from_dispatch(dispatch, item),
                retry_gateway_job_id=dispatch.gateway_job_id,
                attempt_no=dispatch.delivery_attempts,
            )
        except Exception:
            self.session.rollback()
            raise

    def succeed(
        self,
        claim: DeliveryClaim,
        result: GatewayDispatchResult,
    ) -> None:
        try:
            dispatch, item = self._fence(claim)
            if (
                result.gateway_id != dispatch.gateway_id
                or result.external_job_id != dispatch.external_job_id
                or not result.gateway_job_id.strip()
            ):
                raise ProductCollectionLeaseLostError()
            dispatch.gateway_job_id = result.gateway_job_id
            dispatch.state = "dispatched"
            dispatch.lease_id = None
            dispatch.lease_expires_at = None
            dispatch.last_heartbeat_at = None
            dispatch.next_attempt_at = None
            dispatch.last_error_code = None
            dispatch.last_error_stage = None
            dispatch.last_error_message = None
            dispatch.finished_at = None
            item.state = "dispatched"
            item.finished_at = None
            item.last_error_code = None
            item.last_error_stage = None
            item.last_error_message = None
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def fail(
        self,
        claim: DeliveryClaim,
        *,
        error_code: str,
        error_message: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> bool:
        if retry_delay_seconds < 0:
            raise ValueError("Dispatch retry delay cannot be negative")
        try:
            dispatch, item = self._fence(claim)
            now = self.repository.now()
            retryable = dispatch.delivery_attempts < max_attempts
            dispatch.lease_id = None
            dispatch.lease_expires_at = None
            dispatch.last_heartbeat_at = None
            dispatch.last_error_code = error_code.strip()[:96]
            dispatch.last_error_stage = "gateway_delivery"
            dispatch.last_error_message = " ".join(error_message.split())[:500]
            if retryable:
                dispatch.state = "pending_delivery"
                dispatch.next_attempt_at = now + timedelta(seconds=retry_delay_seconds)
                dispatch.finished_at = None
                item.state = "dispatching"
                item.finished_at = None
            else:
                dispatch.state = "delivery_failed"
                dispatch.next_attempt_at = None
                dispatch.finished_at = now
                item.state = "failed"
                item.finished_at = now
                item.last_error_code = dispatch.last_error_code
                item.last_error_stage = dispatch.last_error_stage
                item.last_error_message = dispatch.last_error_message
                self.repository.refresh_request_state(
                    request_id=item.request_id,
                    team_id=item.team_id,
                    at=now,
                )
            self.session.commit()
            return retryable
        except Exception:
            self.session.rollback()
            raise

    def deliver_once(
        self,
        gateway: ProductCollectionGateway,
        *,
        lease_seconds: int,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> bool:
        claim = self.claim(lease_seconds=lease_seconds, max_attempts=max_attempts)
        if claim is None:
            return False
        try:
            result = (
                gateway.retry(gateway_job_id=claim.retry_gateway_job_id)
                if claim.retry_gateway_job_id is not None
                else gateway.deliver(claim.command)
            )
        except Exception as error:
            terminal_attempt_budget = (
                claim.attempt_no
                if getattr(error, "retryable", True) is False
                else max_attempts
            )
            self.fail(
                claim,
                error_code=getattr(
                    error,
                    "failure_code",
                    "PRODUCT_COLLECTION_GATEWAY_UNAVAILABLE",
                ),
                error_message=getattr(
                    error,
                    "safe_message",
                    "手机采集网关暂不可用",
                ),
                max_attempts=terminal_attempt_budget,
                retry_delay_seconds=retry_delay_seconds,
            )
            raise ProductCollectionGatewayUnavailableError() from error
        self.succeed(claim, result)
        return True

    def cancel_requested_once(self, gateway: ProductCollectionGateway) -> bool:
        """Honor one durable human cancel intent without claiming physical retraction."""

        try:
            row = self.session.execute(
                select(Dispatch, Item, CollectionRequest)
                .join(Item, Item.item_id == Dispatch.item_id)
                .join(CollectionRequest, CollectionRequest.request_id == Item.request_id)
                .where(
                    CollectionRequest.cancel_requested_at.is_not(None),
                    Dispatch.state.in_(("pending_delivery", "delivering", "dispatched", "running")),
                    Item.state.in_(("dispatching", "dispatched", "running")),
                    Item.current_dispatch_id == Dispatch.dispatch_id,
                )
                .order_by(CollectionRequest.cancel_requested_at, Dispatch.dispatch_id)
                .with_for_update(skip_locked=True)
                .limit(1),
            ).one_or_none()
            if row is None:
                self.session.rollback()
                return False
            dispatch, item, request = row
            gateway_job_id = dispatch.gateway_job_id
            dispatch_id = dispatch.dispatch_id
            team_id = dispatch.team_id
            if gateway_job_id is None:
                self._finish_canceled(dispatch, item, request)
                self.session.commit()
                return True
            self.session.rollback()
            gateway.cancel(gateway_job_id=gateway_job_id)
            dispatch = self.repository.lock_dispatch(dispatch_id, team_id)
            if dispatch is None:
                raise ProductCollectionLeaseLostError()
            item = self.repository.lock_item(dispatch.item_id, team_id)
            if (
                item is None
                or item.current_dispatch_id != dispatch.dispatch_id
                or dispatch.state not in {"pending_delivery", "delivering", "dispatched", "running"}
                or item.state not in {"dispatching", "dispatched", "running"}
            ):
                self.session.rollback()
                return True
            request = self.repository.lock_request(item.request_id, team_id)
            if request is None or request.cancel_requested_at is None:
                raise ProductCollectionLeaseLostError()
            self._finish_canceled(dispatch, item, request)
            self.session.commit()
            return True
        except Exception:
            self.session.rollback()
            raise

    def _finish_canceled(
        self,
        dispatch: Dispatch,
        item: Item,
        request: CollectionRequest,
    ) -> None:
        now = self.repository.now()
        dispatch.state = "canceled"
        dispatch.finished_at = now
        dispatch.lease_id = None
        dispatch.lease_expires_at = None
        dispatch.last_heartbeat_at = None
        dispatch.next_attempt_at = None
        item.state = "canceled"
        item.finished_at = now
        attempt = self.session.scalar(
            select(CaptureAttempt)
            .where(
                CaptureAttempt.dispatch_id == dispatch.dispatch_id,
                CaptureAttempt.state.in_(("registered", "running")),
            )
            .with_for_update(),
        )
        if attempt is not None:
            attempt.state = "canceled"
            attempt.finished_at = now
        self.repository.refresh_request_state(
            request_id=request.request_id,
            team_id=request.team_id,
            at=now,
        )

    def _fence(self, claim: DeliveryClaim) -> tuple[Dispatch, Item]:
        dispatch = self.session.scalar(
            select(Dispatch)
            .where(
                Dispatch.dispatch_id == claim.dispatch_id,
                Dispatch.state == "delivering",
                Dispatch.lease_id == claim.lease_id,
                Dispatch.lease_expires_at > func.clock_timestamp(),
            )
            .with_for_update()
            .execution_options(populate_existing=True),
        )
        if dispatch is None:
            raise ProductCollectionLeaseLostError()
        item = self.repository.lock_item(dispatch.item_id, dispatch.team_id)
        if item is None or item.current_dispatch_id != dispatch.dispatch_id:
            raise ProductCollectionLeaseLostError()
        return dispatch, item


def exists_active_dispatch(item_id):
    from sqlalchemy import exists

    return exists(
        select(Dispatch.dispatch_id).where(
            Dispatch.item_id == item_id,
            Dispatch.state.in_(("pending_delivery", "delivering", "dispatched", "running")),
        ),
    )


def build_dispatch_command(
    dispatch_id: UUID,
    item: Item,
    *,
    recapture: bool = False,
) -> GatewayDispatchCommand:
    external_job_id = f"pcd_v1_{dispatch_id.hex}"
    payload = {
        "version": 1,
        "external_job_id": external_job_id,
        "dispatch_id": str(dispatch_id),
        "source_platform": item.platform,
        "source_product_id": item.source_product_id,
        "ingest_mode": "central_ingest_v1",
        "job_type": "product",
        "recapture": recapture,
        "priority": 0,
        "max_attempts": 3,
    }
    return GatewayDispatchCommand(
        dispatch_id=dispatch_id,
        external_job_id=external_job_id,
        canonical_payload_hash=canonical_sha256(payload),
        source_platform=SourcePlatform(item.platform),
        source_product_id=item.source_product_id,
        recapture=recapture,
    )


def command_from_dispatch(
    dispatch: Dispatch,
    item: Item,
) -> GatewayDispatchCommand:
    """Rebuild the frozen wire command without changing its idempotency hash."""

    return GatewayDispatchCommand(
        dispatch_id=dispatch.dispatch_id,
        external_job_id=dispatch.external_job_id,
        canonical_payload_hash=dispatch.canonical_payload_hash,
        source_platform=SourcePlatform(item.platform),
        source_product_id=item.source_product_id,
        # A new dispatch after the first one can only be created by the
        # explicit recapture endpoint. Finite retry always reuses dispatch_no.
        recapture=dispatch.dispatch_no > 1,
    )
