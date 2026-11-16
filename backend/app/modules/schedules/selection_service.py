"""Server selection target of the existing Schedule domain; not another scheduler."""

from dataclasses import dataclass
from datetime import UTC, datetime, time
from uuid import UUID, uuid5

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.modules.access.service import ActorContextService
from app.modules.product_selection.models import ProductSelectionStrategy as Strategy
from app.modules.product_selection.run_contract import SelectionRunCreate
from app.modules.product_selection.run_service import SelectionRunService, safe_run_error
from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.product_selection.strategy_contract import SelectionStrategyConditions, SelectionStrategySchedule
from app.modules.schedules.enums import ScheduleRunTriggerResult
from app.modules.schedules.exceptions import ScheduleRuleInvalidError
from app.modules.schedules.models import Schedule, ScheduleRun
from app.modules.schedules.repository import ScheduleRepository
from app.modules.schedules.schemas import ScheduleTriggerSummary
from app.modules.schedules.time_rules import (
    next_hourly_occurrence, latest_hourly_occurrence, next_daily_occurrence, latest_daily_occurrence,
)


@dataclass(frozen=True)
class SelectionDueSnapshot:
    schedule_id: UUID
    strategy_id: UUID
    team_id: UUID
    user_id: UUID
    shop_id: UUID
    strategy_version: int
    schedule_updated_at: datetime
    next_run_at: datetime
    conditions: dict
    schedule_config: dict


class SelectionScheduleService:
    def __init__(self, session: Session, *, settings: Settings | None = None):
        self.session = session
        self.repository = ScheduleRepository(session)
        self.settings = settings or get_settings()

    def sync_strategy(self, strategy: Strategy, *, now: datetime) -> Schedule | None:
        """Save/enable only a future Schedule; no category or platform request."""
        config = SelectionStrategySchedule.model_validate(strategy.schedule_config)
        plan = self.repository.selection_plan(strategy.strategy_id, lock=True)
        if plan is None and not config.scheduled:
            return None
        if plan is not None and (plan.team_id != strategy.team_id or plan.created_by_user_id != strategy.created_by_user_id):
            raise ScheduleRuleInvalidError()
        clock_time = time.fromisoformat(config.daily_time) if config.kind == 'daily' else None
        interval = config.interval_hours if config.kind == 'hourly' else None
        enabled = strategy.enabled and config.scheduled
        changed = plan is None or (plan.schedule_type, plan.interval_hours, plan.local_time, plan.timezone) != (config.kind, interval, clock_time, config.timezone)
        activating = plan is None or not plan.enabled
        if plan is None:
            plan = Schedule(team_id=strategy.team_id, created_by_user_id=strategy.created_by_user_id,
                target_kind='server_selection', selection_strategy_id=strategy.strategy_id,
                target_device_id=None, skill_id=None, parameter_preset_id=None, task_input_json={},
                local_date=None, weekdays=[], created_at=now)
            self.repository.add(plan)
        plan.name = plan.execution_display_name = strategy.name
        plan.schedule_type, plan.interval_hours, plan.local_time, plan.timezone = config.kind, interval, clock_time, config.timezone
        if not enabled:
            plan.next_run_at = None
        elif changed or activating or plan.next_run_at is None:
            try:
                plan.next_run_at = (next_hourly_occurrence(config.timezone, after=now, interval_hours=config.interval_hours)
                    if config.kind == 'hourly' else next_daily_occurrence(clock_time, config.timezone, after=now))
            except ValueError:
                raise ScheduleRuleInvalidError() from None
        # Name/conditions-only edits preserve the existing cadence anchor.
        plan.enabled, plan.updated_at = enabled, now
        self.session.flush()
        return plan

    def _snapshot(self, now: datetime) -> SelectionDueSnapshot | None:
        plan = self.repository.next_selection_due(now=now)
        if plan is None: return None
        strategy = self.session.get(Strategy, plan.selection_strategy_id)
        return SelectionDueSnapshot(plan.schedule_id, strategy.strategy_id, plan.team_id,
            plan.created_by_user_id, strategy.request_shop_id, strategy.version, plan.updated_at,
            plan.next_run_at, dict(strategy.conditions), dict(strategy.schedule_config))

    def _actor(self, snapshot: SelectionDueSnapshot):
        current = ActorContextService(self.session).resolve(user_id=snapshot.user_id, requested_team_id=snapshot.team_id)
        facts = ProductSelectionFactService(self.session)
        current = facts._current_actor(current)
        facts._execution_shop(current, snapshot.shop_id)
        return current

    def trigger_next_due(self, *, now: datetime | None = None, category_reader=None) -> ScheduleTriggerSummary | None:
        if not (self.settings.product_selection_schedule_enabled and self.settings.product_selection_execution_enabled):
            return None
        boundary = now or datetime.now(UTC)
        snapshot = self._snapshot(boundary)
        self.session.rollback()  # End snapshot/read transaction before I/O.
        if snapshot is None: return None
        error, tree = None, None
        try:
            current = self._actor(snapshot)
            config = SelectionStrategySchedule.model_validate(snapshot.schedule_config)
            SelectionStrategyConditions.model_validate(snapshot.conditions).original(snapshot.shop_id)
            self.session.rollback()
            if not config.scheduled:
                tree = None  # Final lock will disable the stale plan; zero platform I/O.
            elif category_reader is None:
                from app.core.database import get_session_factory
                from app.modules.product_selection.category_service import SelectionCategoryService
                tree = SelectionCategoryService(get_session_factory()).read(current, snapshot.shop_id)
            else:
                tree = category_reader(current, snapshot.shop_id)
        except AppError as failure:
            error = failure
        except Exception:
            error = ScheduleRuleInvalidError()
        finally:
            self.session.rollback()
        try:
            # Same order as edits/manual submission, never Schedule→Strategy.
            strategy = self.session.scalar(select(Strategy).where(Strategy.strategy_id == snapshot.strategy_id).with_for_update().execution_options(populate_existing=True))
            plan = self.repository.selection_plan(snapshot.strategy_id, lock=True)
            at = now or self.session.scalar(select(func.clock_timestamp()))
            if (strategy is None or plan is None or plan.schedule_id != snapshot.schedule_id
                or not plan.enabled or not strategy.enabled or plan.next_run_at is None or plan.next_run_at > at
                or plan.updated_at != snapshot.schedule_updated_at or plan.next_run_at != snapshot.next_run_at
                or strategy.version != snapshot.strategy_version or strategy.team_id != snapshot.team_id
                or strategy.created_by_user_id != snapshot.user_id or plan.team_id != strategy.team_id
                or plan.created_by_user_id != strategy.created_by_user_id or strategy.request_shop_id != snapshot.shop_id
                or strategy.conditions != snapshot.conditions or strategy.schedule_config != snapshot.schedule_config):
                self.session.rollback(); return None
            config = SelectionStrategySchedule.model_validate(strategy.schedule_config)
            if not config.scheduled:
                plan.enabled, plan.next_run_at = False, None
                self.session.commit(); return None
            if config.kind == 'hourly':
                scheduled_for = latest_hourly_occurrence(config.timezone, at_or_before=at, interval_hours=config.interval_hours, anchor=plan.next_run_at)
                following = next_hourly_occurrence(config.timezone, after=at, interval_hours=config.interval_hours, anchor=plan.next_run_at)
            else:
                scheduled_for = latest_daily_occurrence(time.fromisoformat(config.daily_time), config.timezone, at_or_before=at)
                following = next_daily_occurrence(time.fromisoformat(config.daily_time), config.timezone, after=at)
            audit = ScheduleRun(schedule_id=plan.schedule_id, scheduled_for=scheduled_for, task_id=None,
                selection_run_id=None, trigger_result='blocked', created_at=at)
            if error is None:
                try:
                    current = self._actor(snapshot)
                    original = SelectionStrategyConditions.model_validate(strategy.conditions).original(snapshot.shop_id)
                    key = uuid5(plan.schedule_id, 'server_selection:' + scheduled_for.astimezone(UTC).isoformat())
                    command = SelectionRunCreate(**original.model_dump(), submission_key=key,
                        strategy_id=strategy.strategy_id, strategy_version=strategy.version)
                    receipt = SelectionRunService(self.session, settings=self.settings).create_for_schedule(current, command, tree=tree, at=at)
                    audit.selection_run_id, audit.trigger_result = receipt.receipt_id, 'selection_run'
                except AppError as failure:
                    error = failure
            if error is not None:
                code, stage, _ = safe_run_error(error)
                audit.trigger_error_code = code
                # Never store error.message, raw exception, URL or platform payload.
                audit.trigger_error_message = stage
            plan.next_run_at, plan.updated_at = following, at
            self.repository.add_run(audit)
            self.session.commit()
            return ScheduleTriggerSummary(run_id=audit.run_id, schedule_id=plan.schedule_id,
                scheduled_for=scheduled_for, trigger_result=ScheduleRunTriggerResult(audit.trigger_result),
                task_id=None, selection_run_id=audit.selection_run_id)
        except Exception:
            self.session.rollback(); raise
