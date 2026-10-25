"""Human-authorized collection submission and product-library query services."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.module_access import ModuleCode
from app.modules.access.service import ModuleAccessService
from app.modules.product_collection.contracts import (
    CandidateCollectionSource,
    ProductCollectionRequestCreate,
    SourcePlatform,
    canonical_sha256,
)
from app.modules.product_collection.exceptions import (
    ProductCollectionCandidateNotFoundError,
    ProductCollectionConfigurationError,
    ProductCollectionGroupNotFoundError,
    ProductCollectionRequestNotFoundError,
    ProductCollectionStateConflictError,
    ProductCollectionSubmissionConflictError,
    ProductLibraryFilterConflictError,
    ProductLibraryProductNotFoundError,
)
from app.modules.product_collection.dispatch_service import build_dispatch_command, command_from_dispatch
from app.modules.product_collection.ports import GATEWAY_CAPTURE_MAX_ATTEMPTS
from app.modules.product_collection.human_contracts import (
    ProductCollectionItemRead,
    ProductCollectionRequestRead,
    ProductCollectionRequestReceipt,
    ProductLibraryProductDetail,
)
from app.modules.product_collection.human_repository import (
    ProductCollectionHumanRepository,
)
from app.modules.product_collection.models import (
    ProductCollectionDispatch as Dispatch,
    ProductCollectionItem as Item,
    ProductCollectionRequest as CollectionRequest,
)
from app.modules.product_collection.targets import distinct_targets
from app.shared.identifiers import generate_id


@dataclass(frozen=True, slots=True)
class _ResolvedTarget:
    platform: SourcePlatform
    source_product_id: str
    candidate_id: UUID | None


class ProductCollectionHumanService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ProductCollectionHumanRepository(session)
        self.module_access = ModuleAccessService(session)

    def create_request(
        self,
        actor: ActorContext,
        command: ProductCollectionRequestCreate,
    ) -> ProductCollectionRequestReceipt:
        team_id = self._write_team(actor)
        targets = self._resolve_targets(actor, command)
        canonical_hash = _normalized_request_hash(command, targets)
        existing = self.repository.find_submission(
            team_id=team_id,
            user_id=actor.user_id,
            submission_key=command.submission_key,
        )
        if existing is not None:
            return self._submission_receipt(existing, canonical_hash, reused=True)

        if command.target_group_id is not None and self.repository.group(
            team_id=team_id,
            group_id=command.target_group_id,
        ) is None:
            raise ProductCollectionGroupNotFoundError()

        request = CollectionRequest(
            request_id=generate_id(),
            team_id=team_id,
            requested_by_user_id=actor.user_id,
            submission_key=command.submission_key,
            source_kind=command.source.kind.value,
            target_group_id=command.target_group_id,
            canonical_request_hash=canonical_hash,
            status="pending",
            item_count=len(targets),
        )
        self.session.add(request)
        try:
            self.session.flush()
            for target in targets:
                current = self.repository.current_product(
                    team_id=team_id,
                    platform=target.platform.value,
                    source_product_id=target.source_product_id,
                )
                self.session.add(
                    Item(
                        item_id=generate_id(),
                        request_id=request.request_id,
                        team_id=team_id,
                        candidate_id=target.candidate_id,
                        platform=target.platform.value,
                        source_product_id=target.source_product_id,
                        collection_mode=(
                            "auto_gateway"
                            if target.platform is SourcePlatform.DOUYIN
                            else "manual_return"
                        ),
                        target_group_id=command.target_group_id,
                        state="pending_dispatch",
                        current_dispatch_id=None,
                        library_product_id=current.product_id if current is not None else None,
                        expected_manual_revision=(
                            current.manual_revision if current is not None else None
                        ),
                        attempt_count=0,
                    ),
                )
            self.session.commit()
        except IntegrityError:
            # Concurrent replays are resolved through the database unique key;
            # a different request using the same submission key still fails closed.
            self.session.rollback()
            existing = self.repository.find_submission(
                team_id=team_id,
                user_id=actor.user_id,
                submission_key=command.submission_key,
            )
            if existing is None:
                raise
            return self._submission_receipt(existing, canonical_hash, reused=True)
        except Exception:
            self.session.rollback()
            raise
        return ProductCollectionRequestReceipt(
            request_id=request.request_id,
            status=request.status,
            item_count=request.item_count,
            reused=False,
        )

    def get_request(
        self,
        actor: ActorContext,
        request_id: UUID,
        *,
        include_items: bool = True,
    ) -> ProductCollectionRequestRead:
        self.module_access.require_module_access(actor, ModuleCode.PRODUCT_LIBRARY)
        request = self.repository.request_for_actor(actor=actor, request_id=request_id)
        if request is None:
            raise ProductCollectionRequestNotFoundError()
        return self._request_read(request, include_items=include_items)

    def list_requests(
        self,
        actor: ActorContext,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[ProductCollectionRequestRead], int]:
        self.module_access.require_module_access(actor, ModuleCode.PRODUCT_LIBRARY)
        rows, total = self.repository.list_requests(
            actor=actor,
            offset=offset,
            limit=limit,
        )
        return [self._request_read(row, include_items=False) for row in rows], total

    def cancel_request(
        self,
        actor: ActorContext,
        request_id: UUID,
    ) -> ProductCollectionRequestRead:
        self._write_team(actor)
        try:
            request = self.repository.request_for_actor(
                actor=actor,
                request_id=request_id,
                lock=True,
            )
            if request is None:
                raise ProductCollectionRequestNotFoundError()
            if request.status not in {"partial", "succeeded", "failed", "canceled"}:
                now = self.session.scalar(select(func.clock_timestamp()))
                request.cancel_requested_at = now
                request.cancel_requested_by_user_id = actor.user_id
                items = self.repository.request_items(
                    team_id=request.team_id,
                    request_id=request.request_id,
                )
                for item in items:
                    if item.state == "pending_dispatch" and item.current_dispatch_id is None:
                        item.state = "canceled"
                        item.finished_at = now
                _refresh_request_from_items(request, items, now)
            self.session.commit()
            return self._request_read(request, include_items=True)
        except Exception:
            self.session.rollback()
            raise

    def retry_item(
        self,
        actor: ActorContext,
        item_id: UUID,
        *,
        max_delivery_attempts: int,
        max_capture_attempts: int,
    ) -> ProductCollectionRequestRead:
        self._write_team(actor)
        try:
            item = self.repository.item_for_actor(actor=actor, item_id=item_id, lock=True)
            if item is None:
                from app.modules.product_collection.exceptions import (
                    ProductCollectionItemNotFoundError,
                )

                raise ProductCollectionItemNotFoundError()
            dispatch = (
                self.session.scalar(
                    select(Dispatch)
                    .where(
                        Dispatch.dispatch_id == item.current_dispatch_id,
                        Dispatch.team_id == item.team_id,
                    )
                    .with_for_update(),
                )
                if item.current_dispatch_id is not None
                else None
            )
            can_retry_delivery = (
                dispatch is not None
                and dispatch.state == "delivery_failed"
                and dispatch.delivery_attempts < max_delivery_attempts
            )
            can_retry_execution = (
                dispatch is not None
                and dispatch.state == "execution_failed"
                and dispatch.gateway_job_id is not None
                and item.attempt_count < max_capture_attempts
                and item.attempt_count < command_from_dispatch(dispatch, item).max_attempts
            )
            if not (can_retry_delivery or can_retry_execution):
                raise ProductCollectionStateConflictError(
                    "当前失败不能通过有限重试恢复，请使用重新采集或检查失败原因",
                )
            dispatch.state = "pending_delivery"
            dispatch.next_attempt_at = self.session.scalar(select(func.clock_timestamp()))
            dispatch.lease_id = None
            dispatch.lease_expires_at = None
            dispatch.finished_at = None
            item.state = "dispatching"
            item.finished_at = None
            request = self.repository.request_for_actor(
                actor=actor,
                request_id=item.request_id,
                lock=True,
            )
            if request is None:
                raise ProductCollectionRequestNotFoundError()
            request.status = "running"
            request.finished_at = None
            self.session.commit()
            return self._request_read(request, include_items=True)
        except Exception:
            self.session.rollback()
            raise

    def recapture_item(
        self,
        actor: ActorContext,
        item_id: UUID,
        *,
        gateway_id: str | None,
        max_capture_attempts: int = GATEWAY_CAPTURE_MAX_ATTEMPTS,
    ) -> ProductCollectionRequestRead:
        self._write_team(actor)
        if gateway_id is None or not gateway_id.strip():
            raise ProductCollectionConfigurationError()
        try:
            item = self.repository.item_for_actor(actor=actor, item_id=item_id, lock=True)
            if item is None:
                from app.modules.product_collection.exceptions import (
                    ProductCollectionItemNotFoundError,
                )

                raise ProductCollectionItemNotFoundError()
            if item.collection_mode != "auto_gateway":
                raise ProductCollectionStateConflictError(
                    "当前平台只登记人工回传边界，不能创建自动采集派发",
                )
            current = (
                self.session.scalar(
                    select(Dispatch)
                    .where(
                        Dispatch.dispatch_id == item.current_dispatch_id,
                        Dispatch.team_id == item.team_id,
                    )
                    .with_for_update(),
                )
                if item.current_dispatch_id is not None
                else None
            )
            if current is not None and current.state in {
                "pending_delivery",
                "delivering",
                "dispatched",
                "running",
            }:
                raise ProductCollectionStateConflictError("当前商品已有进行中的采集任务")
            request = self.repository.request_for_actor(
                actor=actor,
                request_id=item.request_id,
                lock=True,
            )
            if request is None:
                raise ProductCollectionRequestNotFoundError()
            # Serialize with new cancel requests. Transaction-start now() may
            # predate a cancel committed while this request was waiting.
            recaptured_at = self.session.scalar(select(func.clock_timestamp()))
            dispatch_no = self.session.scalar(
                select(func.coalesce(func.max(Dispatch.dispatch_no), 0)).where(
                    Dispatch.item_id == item.item_id,
                ),
            ) + 1
            dispatch_id = generate_id()
            command = build_dispatch_command(
                dispatch_id, item, recapture=True, max_attempts=max_capture_attempts,
            )
            dispatch = Dispatch(
                dispatch_id=dispatch_id,
                item_id=item.item_id,
                team_id=item.team_id,
                dispatch_no=dispatch_no,
                external_job_id=command.external_job_id,
                canonical_payload_hash=command.canonical_payload_hash,
                gateway_id=gateway_id.strip(),
                state="pending_delivery",
                delivery_attempts=0,
                created_at=recaptured_at,
                updated_at=recaptured_at,
            )
            self.session.add(dispatch)
            self.session.flush()
            current_product = self.repository.current_product(
                team_id=item.team_id,
                platform=item.platform,
                source_product_id=item.source_product_id,
            )
            item.current_dispatch_id = dispatch.dispatch_id
            item.expected_manual_revision = (
                current_product.manual_revision if current_product is not None else None
            )
            item.state = "dispatching"
            item.finished_at = None
            item.last_error_code = None
            item.last_error_stage = None
            item.last_error_message = None
            request.status = "running"
            request.finished_at = None
            self.session.commit()
            return self._request_read(request, include_items=True)
        except Exception:
            self.session.rollback()
            raise

    def list_groups(self, actor: ActorContext):
        self._read_team(actor)
        return self.repository.list_groups(actor=actor)

    def list_products(
        self,
        actor: ActorContext,
        *,
        offset: int,
        limit: int,
        search: str | None,
        group_id: UUID | None,
        ungrouped: bool,
    ):
        self._read_team(actor)
        if group_id is not None and ungrouped:
            raise ProductLibraryFilterConflictError()
        if group_id is not None and self.repository.group(
            team_id=actor.require_team_id(),
            group_id=group_id,
        ) is None:
            raise ProductCollectionGroupNotFoundError()
        return self.repository.list_products(
            actor=actor,
            offset=offset,
            limit=limit,
            search=search,
            group_id=group_id,
            ungrouped=ungrouped,
        )

    def get_product(
        self,
        actor: ActorContext,
        product_id: UUID,
    ) -> ProductLibraryProductDetail:
        team_id = self._read_team(actor)
        product = self.repository.product_for_actor(actor=actor, product_id=product_id)
        if product is None:
            raise ProductLibraryProductNotFoundError()
        versions = self.repository.product_versions(
            team_id=team_id,
            product_id=product.product_id,
        )
        latest_item = self.repository.latest_item_for_product(
            team_id=team_id,
            product=product,
        )
        return ProductLibraryProductDetail.model_validate(
            {
                **{
                    key: getattr(product, key)
                    for key in ProductLibraryProductDetail.model_fields
                    if key not in {
                        "versions",
                        "latest_collection_state",
                        "latest_collection_error_code",
                    }
                },
                "versions": versions,
                "latest_collection_state": latest_item.state if latest_item else None,
                "latest_collection_error_code": (
                    latest_item.last_error_code if latest_item else None
                ),
            },
        )

    def _resolve_targets(
        self,
        actor: ActorContext,
        command: ProductCollectionRequestCreate,
    ) -> tuple[_ResolvedTarget, ...]:
        if isinstance(command.source, CandidateCollectionSource):
            requested_ids = tuple(dict.fromkeys(command.source.candidate_ids))
            candidates = self.repository.visible_candidates(
                actor=actor,
                candidate_ids=requested_ids,
            )
            by_id = {candidate.candidate_id: candidate for candidate in candidates}
            if set(by_id) != set(requested_ids):
                raise ProductCollectionCandidateNotFoundError()
            return tuple(
                _ResolvedTarget(
                    platform=SourcePlatform(by_id[candidate_id].platform),
                    source_product_id=by_id[candidate_id].platform_product_id,
                    candidate_id=candidate_id,
                )
                for candidate_id in requested_ids
            )
        return tuple(
            _ResolvedTarget(target.platform, target.source_product_id, None)
            for target in distinct_targets(command.source.targets)
        )

    def _submission_receipt(
        self,
        request: CollectionRequest,
        expected_hash: str,
        *,
        reused: bool,
    ) -> ProductCollectionRequestReceipt:
        if request.canonical_request_hash != expected_hash:
            raise ProductCollectionSubmissionConflictError()
        return ProductCollectionRequestReceipt(
            request_id=request.request_id,
            status=request.status,
            item_count=request.item_count,
            reused=reused,
        )

    def _request_read(
        self,
        request: CollectionRequest,
        *,
        include_items: bool,
    ) -> ProductCollectionRequestRead:
        counts = self.repository.request_counts(
            team_id=request.team_id,
            request_id=request.request_id,
        )
        items = (
            [
                ProductCollectionItemRead.model_validate(item)
                for item in self.repository.request_items(
                    team_id=request.team_id,
                    request_id=request.request_id,
                )
            ]
            if include_items
            else None
        )
        return ProductCollectionRequestRead(
            request_id=request.request_id,
            submission_key=request.submission_key,
            source_kind=request.source_kind,
            target_group_id=request.target_group_id,
            status=request.status,
            cancel_requested_at=request.cancel_requested_at,
            created_at=request.created_at,
            updated_at=request.updated_at,
            finished_at=request.finished_at,
            items=items,
            **counts,
        )

    def _write_team(self, actor: ActorContext) -> UUID:
        self.module_access.require_module_access(actor, ModuleCode.PRODUCT_LIBRARY)
        return actor.require_team_id()

    def _read_team(self, actor: ActorContext) -> UUID:
        return self._write_team(actor)


def _normalized_request_hash(
    command: ProductCollectionRequestCreate,
    targets: tuple[_ResolvedTarget, ...],
) -> str:
    return canonical_sha256(
        {
            "submission_key": str(command.submission_key),
            "target_group_id": (
                str(command.target_group_id) if command.target_group_id is not None else None
            ),
            "source_kind": command.source.kind.value,
            "targets": sorted(
                (
                    target.platform.value,
                    target.source_product_id,
                    str(target.candidate_id) if target.candidate_id is not None else None,
                )
                for target in targets
            ),
        },
    )


def _refresh_request_from_items(
    request: CollectionRequest,
    items: list[Item],
    at,
) -> None:
    terminal = {"succeeded", "failed", "canceled"}
    states = [item.state for item in items]
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
