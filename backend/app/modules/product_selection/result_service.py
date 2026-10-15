"""Rank-only immutable hits and scoped result reads; never network or a queue."""

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
import json
from zoneinfo import ZoneInfo

from app.modules.product_selection.models import (
    ProductSelectionResultItem as Item,
)
from app.modules.product_selection.run_contract import custom_price_bin
from app.modules.product_selection.run_repository import SelectionRunRepository
from app.modules.product_selection.result_repository import SelectionResultRepository
from app.modules.product_selection.result_contract import SelectionRankSnapshot, SelectionBatchRead, SelectionResultContext
from app.modules.product_selection.service import ProductSelectionFactService, _range_fact
from app.modules.product_selection.schemas import SelectionObservationRead
from app.modules.product_selection.exceptions import SelectionRunNotFoundError
from app.modules.product_selection.exceptions import SelectionObservationNotFoundError
from app.modules.schedules.time_rules import view_date_utc_bounds


def discovery_key(team_id, original):
    condition = original.model_dump(mode="json")
    if original.price_mode == "custom":
        lower, upper = custom_price_bin(original).split("-")
        condition.update(price_above=lower, price_below=upper)
    return sha256(json.dumps({"team_id": str(team_id), "conditions": condition},
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class SelectionResultService:
    def __init__(self, session):
        self.session = session
        self.facts = ProductSelectionFactService(session)
        self.runs = SelectionRunRepository(session)
        self.repository = SelectionResultRepository(session)

    def classify(self, candidate_id, run, request):
        key = discovery_key(run.team_id, request.original)
        if self.repository.has_prior_hit(candidate_id, key, run.run_id):
            return key, "known"
        candidate = self.repository.candidate(candidate_id)
        if candidate.discovery_tracking_version == 1:
            return key, "new"
        # Legacy facts prove positive hits only, not an absence of old membership.
        for observation, old_run in self.repository.legacy_evidence(candidate_id, run.team_id, run.request_shop_id):
            try:
                previous = self.runs.validated_request(old_run)
                if (previous.version >= 2 and previous.actual_scope().fingerprint(first_listed_only=previous.original.first_listed_only) == observation.source_scope_hash
                    and discovery_key(old_run.team_id, previous.original) == key):
                    return key, "known"
            except ValueError:
                continue
        return key, "unknown"

    def append_hit(self, *, run, observation_id, key, state, product, at):
        observation = self.repository.observation(observation_id)
        if observation.last_run_id != run.run_id:
            raise ValueError("Result membership must match the fenced rank writer")
        snapshot = SelectionRankSnapshot(
            rank=product.rank, previous_rank=observation.previous_rank,
            previous_checked_at=observation.previous_checked_at, price_band=product.price_band,
            newly_on_ranking=product.newly_on_ranking,
            video_metric_ranges={name: _range_fact(getattr(product, name), at)
                for name in ("pay_amt", "pay_combo_cnt", "product_click_cnt", "video_cnt")})
        self.repository.append(Item(execution_run_id=run.run_id, observation_id=observation_id,
            discovery_scope_hash=key, discovery_state=state, hit_at=at,
            snapshot=snapshot.model_dump(mode="json")))

    def batches(self, actor, strategy_id, *, shop_id=None, offset=0, limit=20):
        from app.modules.product_selection.strategy_service import SelectionStrategyService
        from app.modules.product_selection.run_service import SelectionRunService
        self._pagination(offset, limit)
        current, _ = SelectionStrategyService(self.session).existing_context(actor, strategy_id)
        pairs, total = self.repository.batches(current, strategy_id, shop_id=shop_id, offset=offset, limit=limit)
        counts = self.repository.visible_counts(current, [execution.run_id for _, execution in pairs if execution.result_detail_version is not None])
        service = SelectionRunService(self.session)
        return [SelectionBatchRead(receipt_id=row.run_id, execution_run_id=execution.run_id,
            submitted_at=row.created_at,
            detail_state="recorded" if execution.result_detail_version is not None else "not_recorded",
            visible_item_count=counts.get(execution.run_id, 0) if execution.result_detail_version is not None else None,
            execution=service._read(current, row)) for row, execution in pairs], total

    def _batch(self, actor, receipt_id, strategy_id):
        from app.modules.product_selection.run_service import SelectionRunService
        current = self.facts._current_actor(actor)
        lookup = replace(current, team_id=None) if current.is_super_account else current
        receipt = self.runs.get_for_actor(lookup, receipt_id)
        if receipt is None:
            raise SelectionRunNotFoundError()
        if current.is_super_account:
            current = self.facts._current_actor(replace(current, team_id=receipt.team_id))
        pair = self.runs.receipts_for_actor(current, [receipt_id]).get(receipt_id)
        if pair is None:
            raise SelectionRunNotFoundError()
        receipt, execution = pair
        if receipt.operation_kind != "rank" or execution.operation_kind != "rank" or (strategy_id is not None and receipt.strategy_id != strategy_id):
            raise SelectionRunNotFoundError()
        self.runs.validated_request(receipt)
        self.runs.validated_request(execution)
        return current, execution, SelectionResultContext(receipt_id=receipt_id, execution_run_id=execution.run_id,
            detail_state="recorded" if execution.result_detail_version is not None else "not_recorded",
            execution=SelectionRunService(self.session)._read(current, receipt))

    @staticmethod
    def _pagination(offset, limit):
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid bounded pagination")

    def get(self, actor, observation_id, *, receipt_id=None):
        current = self.facts._current_actor(actor)
        execution = None
        if receipt_id is not None:
            current, execution, context = self._batch(current, receipt_id, None)
            if context.detail_state != "recorded":
                raise SelectionObservationNotFoundError()
        read = self.facts.get_read(actor=current, observation_id=observation_id)
        item = self.repository.membership(execution.run_id if execution else read.last_run_id, observation_id) if execution or read.last_run_id else None
        if execution is not None and item is None:
            raise SelectionObservationNotFoundError()
        return self._project(read, item, snapshots=execution is not None, execution=execution)

    def _project(self, read, item, *, snapshots, execution=None):
        if item is None:
            return read
        payload = read.model_dump() | {"discovery_state": item.discovery_state, "hit_at": item.hit_at,
            "result_run_id": item.execution_run_id}
        if snapshots:
            snapshot = SelectionRankSnapshot.model_validate(item.snapshot)
            payload.update(snapshot.model_dump(exclude={"version"}), checked_at=item.hit_at, metrics_retrieved_at=item.hit_at)
            if execution is not None:
                request = self.runs.validated_request(execution)
                if request.actual_scope().fingerprint(first_listed_only=request.original.first_listed_only) != read.source_scope_hash:
                    raise SelectionObservationNotFoundError()
                source = request.actual_scope().context(first_listed_only=request.original.first_listed_only)
                if request.provenance() is not None:
                    source["date_selection"] = request.provenance().model_dump(mode="json")
                payload.update(source_context=source, period_begin=request.actual_scope().period_begin, period_end=request.actual_scope().period_end)
        return SelectionObservationRead.model_validate(payload)

    def list(self, actor, *, shop_id=None, blocked=False, result_scope="all", strategy_id=None,
             receipt_id=None, scope_hash=None, search=None, offset=0, limit=10,
             sort="checked_at", descending=True, now=None):
        from app.modules.product_selection.strategy_service import SelectionStrategyService
        self._pagination(offset, limit)
        if result_scope not in {"all", "today", "today_new", "today_known"}:
            raise ValueError("Unknown result scope")
        current = self.facts._current_actor(actor)
        if strategy_id is not None:
            current, _ = SelectionStrategyService(self.session).existing_context(current, strategy_id)
        context, execution = SelectionResultContext(), None
        if receipt_id is not None:
            current, execution, context = self._batch(current, receipt_id, strategy_id)
            if context.detail_state == "not_recorded":
                return [], 0, context
        bounds = None
        if result_scope != "all":
            bounds = view_date_utc_bounds((now or datetime.now(UTC)).astimezone(ZoneInfo("Asia/Shanghai")).date(), "Asia/Shanghai")
        state = {"today_new": "new", "today_known": "known"}.get(result_scope)
        rows, total, unknown, snapshots = self.repository.list(current,
            shop_id=shop_id, blocked=blocked, strategy_id=strategy_id,
            execution_id=execution.run_id if execution else None, day_bounds=bounds, discovery_state=state,
            scope_hash=scope_hash, search=search.strip() if search else None,
            offset=offset, limit=limit, sort=sort, descending=descending)
        reads = self.facts._read_projection([row for row, _ in rows])
        executions = self.repository.executions([item.execution_run_id for _, item in rows if item is not None]) if snapshots and execution is None else {}
        for i, (_, item) in enumerate(rows):
            selected_run = execution or (executions.get(item.execution_run_id) if item is not None else None)
            reads[i] = self._project(reads[i], item, snapshots=snapshots, execution=selected_run)
        context.unknown_discovery_count = unknown
        return reads, total, context
