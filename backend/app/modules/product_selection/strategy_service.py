"""Only saved configuration writes; no platform request or implicit execution."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session
from app.core.config import Settings, get_settings

from app.modules.access.contracts import ActorContext
from app.modules.product_selection.exceptions import SelectionStrategyNotFoundError, SelectionStrategyVersionConflictError, SelectionStrategyWriteDisabledError
from app.modules.product_selection.models import ProductSelectionStrategy
from app.modules.product_selection.request_mapping import validate_preparable_short_video_choice
from app.modules.product_selection.run_contract import SelectionRunRead
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.product_selection.strategy_contract import SelectionStrategyCreate, SelectionStrategyUpdate, SelectionStrategyToggle, SelectionStrategyRead, SelectionStrategyTriggerRead
from app.modules.product_selection.strategy_repository import SelectionStrategyRepository


class SelectionStrategyService:
    def __init__(self, session: Session, *, settings: Settings | None = None):
        self.session = session
        self.repository = SelectionStrategyRepository(session)
        self.facts = ProductSelectionFactService(session)
        self.settings = settings or get_settings()

    def _project(self, actor, rows):
        from app.modules.schedules.repository import ScheduleRepository
        from app.modules.product_selection.run_repository import SelectionRunRepository
        from app.modules.product_selection.run_service import SAFE_ERROR_CODES
        shops = self.repository.shops(rows)
        runs = self.repository.latest_runs(actor, rows)
        schedules = ScheduleRepository(self.session)
        ids = [row.strategy_id for row in rows]
        plans = schedules.selection_plans(ids)
        triggers = schedules.latest_selection_triggers(ids)
        run_repository = SelectionRunRepository(self.session)
        receipts = run_repository.receipts_for_actor(actor, [trigger.selection_run_id for trigger in triggers.values() if trigger.selection_run_id is not None])
        result = []
        for row in rows:
            record = runs.get(row.strategy_id)
            latest, shown_trigger = None, None
            if record is not None:
                run_repository.validated_request(record.receipt)
                run_repository.validated_request(record.execution)
                latest = SelectionRunRead.model_validate(record.execution)
            trigger = triggers.get(row.strategy_id)
            trigger_is_newer = trigger is not None and (record is None
                or (trigger.created_at, str(trigger.run_id)) > (record.receipt.created_at, str(record.receipt.run_id))
                or (trigger.created_at == record.receipt.created_at and trigger.selection_run_id == record.receipt.run_id))
            if trigger_is_newer:
                shown_trigger = SelectionStrategyTriggerRead(schedule_run_id=trigger.run_id, scheduled_for=trigger.scheduled_for,
                    created_at=trigger.created_at, trigger_result="blocked", error_code="PRODUCT_SELECTION_EXECUTION_FAILED", error_stage="execution")
                latest = None
                linked = receipts.get(trigger.selection_run_id)
                if trigger.trigger_result == 'selection_run' and linked is not None:
                    submitted, canonical = linked
                    if submitted.team_id == row.team_id and submitted.strategy_id == row.strategy_id:
                        run_repository.validated_request(submitted)
                        run_repository.validated_request(canonical)
                        latest = SelectionRunRead.model_validate(canonical)
                        shown_trigger = shown_trigger.model_copy(update={"trigger_result":"selection_run", "receipt_id":submitted.run_id,
                            "execution_run_id":canonical.run_id, "error_code":None, "error_stage":None})
                elif trigger.trigger_result == 'blocked':
                    code = trigger.trigger_error_code if trigger.trigger_error_code in SAFE_ERROR_CODES else 'PRODUCT_SELECTION_EXECUTION_FAILED'
                    stage = trigger.trigger_error_message if trigger.trigger_error_message in {'session','signer','http','response_parse','platform_business','authorization','conditions','execution'} else 'execution'
                    shown_trigger = shown_trigger.model_copy(update={"error_code":code,"error_stage":stage})
            plan = plans.get(row.strategy_id)
            result.append(SelectionStrategyRead(
            strategy_id=row.strategy_id, team_id=row.team_id,
            created_by_user_id=row.created_by_user_id, name=row.name,
            shop_id=row.request_shop_id, shop_name=shops[row.request_shop_id],
            version=row.version, enabled=row.enabled, conditions=row.conditions,
            schedule=row.schedule_config, created_at=row.created_at, updated_at=row.updated_at,
            schedule_available=True,
            schedule_execution_enabled=self.settings.product_selection_schedule_enabled and self.settings.product_selection_execution_enabled,
            next_run_at=plan.next_run_at if plan is not None and plan.enabled else None,
            latest_run=latest, latest_trigger=shown_trigger,
            ))
        return result

    def list(self, actor: ActorContext, *, offset: int, limit: int, search: str | None = None):
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid bounded pagination")
        current = self.facts._current_actor(actor)
        rows, total = self.repository.list(current, offset=offset, limit=limit, search=search.strip() if search else None)
        return self._project(current, rows), total

    def get(self, actor: ActorContext, strategy_id: UUID):
        current, row = self.existing_context(actor, strategy_id)
        return self._project(current, [row])[0]

    def existing_context(self, actor: ActorContext, strategy_id: UUID, *, lock: bool = False):
        """Derive a verified super actor's write Team from this saved resource.

        Only direct existing-strategy operations use this rule. List filters,
        new configurations and unassociated manual submissions retain their
        explicit Team context. Never trust a frontend Team or a cached super bit.
        """
        current = self.facts._current_actor(actor)
        lookup = replace(current, team_id=None) if current.is_super_account else current
        row = self.repository.get(lookup, strategy_id, lock=lock)
        if row is None:
            raise SelectionStrategyNotFoundError()
        if current.is_super_account:
            # Re-resolve the saved Team, current User and module authorization.
            # Disabled/missing Teams and revoked super authority fail closed.
            current = self.facts._current_actor(replace(current, team_id=row.team_id))
        if row.team_id != current.require_team_id():
            raise SelectionStrategyNotFoundError()
        return current, row

    def writable(self, actor: ActorContext, strategy_id: UUID, *, expected_version: int):
        """Lock authorized configuration and enforce CAS, not execution readiness."""
        _, row = self.existing_context(actor, strategy_id, lock=True)
        if row.version != expected_version:
            raise SelectionStrategyVersionConflictError()
        return row

    def save(self, actor: ActorContext, command: SelectionStrategyCreate | SelectionStrategyUpdate, *, strategy_id: UUID | None = None):
        try:
            current = self.facts._current_actor(actor)
            if not self.settings.product_selection_strategy_management_enabled:
                raise SelectionStrategyWriteDisabledError()
            if strategy_id is None:
                team_id = current.require_team_id()
            else:
                if not isinstance(command, SelectionStrategyUpdate):
                    raise ValueError("Updates require an expected saved version")
                current, row = self.existing_context(current, strategy_id, lock=True)
                if row.version != command.expected_version:
                    raise SelectionStrategyVersionConflictError()
            # Validate the newly submitted target, not a disabled old target
            # that an authorized configuration edit is trying to replace.
            self.facts._execution_shop(current, command.shop_id)
            validate_preparable_short_video_choice(command.conditions.original(command.shop_id))
            at = datetime.now(UTC)
            if strategy_id is None:
                row = ProductSelectionStrategy(team_id=team_id, created_by_user_id=current.user_id, request_shop_id=command.shop_id, version=1, created_at=at)
                self.session.add(row)
            else:
                row.version += 1
            row.name, row.request_shop_id, row.enabled = command.name, command.shop_id, command.enabled
            row.conditions = command.conditions.model_dump(mode="json")
            row.schedule_config = command.schedule.model_dump(mode="json")
            row.updated_at = at
            self.session.flush()
            from app.modules.schedules.selection_service import SelectionScheduleService
            SelectionScheduleService(self.session, settings=self.settings).sync_strategy(row, now=at)
            result = self._project(current, [row])[0]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise

    def toggle(self, actor: ActorContext, strategy_id: UUID, command: SelectionStrategyToggle):
        try:
            current = self.facts._current_actor(actor)
            if not self.settings.product_selection_strategy_management_enabled:
                raise SelectionStrategyWriteDisabledError()
            current, row = self.existing_context(current, strategy_id, lock=True)
            if row.version != command.expected_version:
                raise SelectionStrategyVersionConflictError()
            if command.enabled:
                self.facts._execution_shop(current, row.request_shop_id)
            row.enabled = command.enabled
            row.version += 1
            row.updated_at = datetime.now(UTC)
            self.session.flush()
            from app.modules.schedules.selection_service import SelectionScheduleService
            SelectionScheduleService(self.session, settings=self.settings).sync_strategy(row, now=row.updated_at)
            result = self._project(current, [row])[0]
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise
