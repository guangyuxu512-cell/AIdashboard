from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.access.contracts import ActorContext
from app.modules.schedules.enums import (
    ScheduleExecutionType,
    ScheduleRunTriggerResult,
    ScheduleType,
)
from app.modules.schedules.exceptions import (
    ScheduleNotFoundError,
    ScheduleRuleInvalidError,
)
from app.modules.schedules.models import Schedule, ScheduleRun, ScheduleShop
from app.modules.schedules.repository import (
    ScheduleListRecord,
    ScheduleRepository,
    ScheduleRunRecord,
)
from app.modules.schedules.schemas import (
    ScheduleCreate,
    ScheduleListItemRead,
    ScheduleRead,
    ScheduleRunRead,
    ScheduleTriggerSummary,
    ScheduleUpdate,
)
from app.modules.schedules.time_rules import (
    latest_schedule_occurrence,
    next_schedule_occurrence,
    validate_schedule_rule,
    view_date_utc_bounds,
)
from app.modules.tasks.enums import TaskSkillId, TaskStatus
from app.modules.tasks.exceptions import TaskInputInvalidError
from app.modules.tasks.schemas import TaskCreate
from app.modules.tasks.service import TaskService
from app.shared.pagination import Page


class ScheduleService:
    def __init__(
        self,
        session: Session,
        repository: ScheduleRepository | None = None,
        task_service: TaskService | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or ScheduleRepository(session)
        self.task_service = task_service or TaskService(session)

    def create(
        self,
        data: ScheduleCreate,
        actor: ActorContext,
        *,
        now: datetime | None = None,
    ) -> ScheduleRead:
        current_time = now or datetime.now(UTC)
        team_id = actor.require_team_id()
        task_data = _task_create(
            target_device_id=data.target_device_id,
            shop_ids=data.shop_ids,
            execution_type=data.execution_type,
            application_id=data.application_id,
            parameter_preset_id=data.parameter_preset_id,
            skill_id=data.skill_id,
            parameters=data.parameters,
        )
        prepared = self.task_service.prepare_scheduled_task(
            task_data,
            team_id=team_id,
            actor=actor,
        )
        schedule = Schedule(
            team_id=team_id,
            created_by_user_id=actor.user_id,
            name=data.name,
            enabled=data.enabled,
            target_device_id=data.target_device_id,
            parameter_preset_id=data.parameter_preset_id,
            skill_id=task_data.skill_id,
            execution_display_name=prepared.execution_display_name,
            schedule_type=data.schedule_type.value,
            local_time=data.local_time,
            timezone=data.timezone,
            local_date=data.local_date,
            weekdays=list(data.weekdays),
            task_input_json=prepared.input_json,
            shop_links=[
                ScheduleShop(shop_id=shop_id, position=position)
                for position, shop_id in enumerate(data.shop_ids)
            ],
            next_run_at=(
                next_schedule_occurrence(
                    data.schedule_type,
                    local_date=data.local_date,
                    local_time=data.local_time,
                    weekdays=data.weekdays,
                    timezone_name=data.timezone,
                    after=current_time,
                )
                if data.enabled
                else None
            ),
        )
        self.repository.add(schedule)
        self.session.commit()
        self.session.refresh(schedule)
        return self.get(actor, schedule.schedule_id)

    def update(
        self,
        schedule_id: UUID,
        data: ScheduleUpdate,
        actor: ActorContext,
        *,
        now: datetime | None = None,
    ) -> ScheduleRead:
        current_time = now or datetime.now(UTC)
        schedule = self.repository.get_for_actor_for_update(
            actor=actor,
            schedule_id=schedule_id,
        )
        if schedule is None or not actor.can_access_team(schedule.team_id):
            raise ScheduleNotFoundError()

        values = data.model_dump(exclude_unset=True)
        only_disabling = set(values) == {"enabled"} and values["enabled"] is False
        if only_disabling:
            schedule.enabled = False
            schedule.next_run_at = None
        else:
            target_device_id = values.get(
                "target_device_id",
                schedule.target_device_id,
            )
            shop_ids = values.get("shop_ids", schedule.shop_ids)
            current_execution_type = _execution_type_for_skill(schedule.skill_id)
            execution_type = values.get(
                "execution_type",
                current_execution_type,
            )
            if execution_type is ScheduleExecutionType.YINGDAO_APPLICATION:
                application_id = values.get("application_id")
                if application_id is None and current_execution_type is execution_type:
                    application_id = str(schedule.task_input_json["app_id"])
                if application_id is None:
                    raise TaskInputInvalidError("请选择影刀应用")
                skill_id = None
                existing_preset_id = (
                    schedule.parameter_preset_id
                    if current_execution_type is execution_type
                    and application_id == schedule.task_input_json.get("app_id")
                    else None
                )
                parameter_preset_id = values.get(
                    "parameter_preset_id",
                    existing_preset_id,
                )
                existing_parameters = (
                    schedule.task_input_json.get("params", {})
                    if current_execution_type is execution_type
                    else {}
                )
                if (
                    existing_preset_id is not None
                    and parameter_preset_id is None
                    and "parameters" not in values
                ):
                    # A preset Task stores a versioned Worker envelope instead of
                    # manual fields.  Clearing the preset must not feed that
                    # envelope back into manual-schema validation.
                    existing_parameters = {}
            else:
                if values.get("parameter_preset_id") is not None:
                    raise TaskInputInvalidError("业务 Skill 不支持影刀参数预设")
                skill_id = values.get("skill_id")
                if skill_id is None and current_execution_type is execution_type:
                    skill_id = schedule.skill_id
                if skill_id is None:
                    raise TaskInputInvalidError("请选择业务 Skill")
                application_id = None
                parameter_preset_id = None
                existing_parameters = (
                    schedule.task_input_json
                    if current_execution_type is execution_type
                    else {}
                )
            parameters = values.get("parameters", existing_parameters)
            task_data = _task_create(
                target_device_id=target_device_id,
                shop_ids=shop_ids,
                execution_type=execution_type,
                application_id=application_id,
                parameter_preset_id=parameter_preset_id,
                skill_id=skill_id,
                parameters=parameters,
            )
            prepared = self.task_service.prepare_scheduled_task(
                task_data,
                team_id=schedule.team_id,
                actor=actor,
            )

            schedule_type = values.get(
                "schedule_type",
                ScheduleType(schedule.schedule_type),
            )
            local_date = values.get("local_date", schedule.local_date)
            weekdays = values.get("weekdays", list(schedule.weekdays))
            if schedule_type is not ScheduleType.ONCE:
                local_date = None
            if schedule_type is not ScheduleType.WEEKLY:
                weekdays = []
            try:
                local_date, weekdays = validate_schedule_rule(
                    schedule_type,
                    local_date,
                    weekdays,
                )
            except ValueError as error:
                raise ScheduleRuleInvalidError() from error

            schedule.name = values.get("name", schedule.name)
            schedule.target_device_id = target_device_id
            schedule.parameter_preset_id = parameter_preset_id
            if schedule.shop_ids != shop_ids:
                # Remove the old ordered set before inserting the replacement.
                # This also makes pure reordering safe with the unique position
                # constraint instead of relying on row update order.
                schedule.shop_links.clear()
                self.session.flush()
                schedule.shop_links = [
                    ScheduleShop(shop_id=shop_id, position=position)
                    for position, shop_id in enumerate(shop_ids)
                ]
            schedule.skill_id = task_data.skill_id
            schedule.execution_display_name = prepared.execution_display_name
            schedule.schedule_type = schedule_type.value
            schedule.local_time = values.get("local_time", schedule.local_time)
            schedule.timezone = values.get("timezone", schedule.timezone)
            schedule.local_date = local_date
            schedule.weekdays = weekdays
            schedule.task_input_json = prepared.input_json
            schedule.enabled = values.get("enabled", schedule.enabled)
            schedule.next_run_at = (
                next_schedule_occurrence(
                    schedule_type,
                    local_date=schedule.local_date,
                    local_time=schedule.local_time,
                    weekdays=schedule.weekdays,
                    timezone_name=schedule.timezone,
                    after=current_time,
                )
                if schedule.enabled
                else None
            )

        self.session.commit()
        return self.get(actor, schedule_id)

    def archive(
        self,
        schedule_id: UUID,
        actor: ActorContext,
        *,
        now: datetime | None = None,
    ) -> None:
        schedule = self.repository.get_for_actor_for_update(
            actor=actor,
            schedule_id=schedule_id,
        )
        if schedule is None or not actor.can_access_team(schedule.team_id):
            raise ScheduleNotFoundError()
        schedule.enabled = False
        schedule.next_run_at = None
        schedule.deleted_at = now or datetime.now(UTC)
        self.session.commit()

    def get(self, actor: ActorContext, schedule_id: UUID) -> ScheduleRead:
        record = self.repository.get_record_for_actor(
            actor=actor,
            schedule_id=schedule_id,
        )
        if record is None:
            raise ScheduleNotFoundError()
        return _schedule_to_read(record)

    def list_management(
        self,
        *,
        actor: ActorContext,
        page: int,
        page_size: int,
        enabled: bool | None,
        device_id: UUID | None,
        search: str | None,
        occurrence_date: date | None = None,
        view_timezone: str | None = None,
    ) -> Page[ScheduleListItemRead]:
        if (occurrence_date is None) != (view_timezone is None):
            raise ValueError("occurrence_date and view_timezone must be supplied together")
        occurrence_start: datetime | None = None
        occurrence_end: datetime | None = None
        if occurrence_date is not None and view_timezone is not None:
            occurrence_start, occurrence_end = view_date_utc_bounds(
                occurrence_date,
                view_timezone,
            )
        normalized_search = search.strip() if search else None
        records, total = self.repository.list_management(
            actor=actor,
            offset=(page - 1) * page_size,
            limit=page_size,
            enabled=enabled,
            device_id=device_id,
            search=normalized_search or None,
            occurrence_start=occurrence_start,
            occurrence_end=occurrence_end,
        )
        return Page(
            items=[_schedule_to_list_item(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    def list_runs(
        self,
        schedule_id: UUID,
        actor: ActorContext,
        *,
        page: int,
        page_size: int,
    ) -> Page[ScheduleRunRead]:
        if self.repository.get_including_deleted_for_actor(
            actor=actor,
            schedule_id=schedule_id,
        ) is None:
            raise ScheduleNotFoundError()
        records, total = self.repository.list_runs(
            schedule_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        return Page(
            items=[_schedule_run_to_read(record) for record in records],
            total=total,
            page=page,
            page_size=page_size,
        )

    def trigger_next_due(
        self,
        *,
        now: datetime | None = None,
    ) -> ScheduleTriggerSummary | None:
        current_time = now or datetime.now(UTC)
        schedule = self.repository.get_next_due(now=current_time)
        if schedule is None:
            self.session.rollback()
            return None

        schedule_type = ScheduleType(schedule.schedule_type)
        scheduled_for = latest_schedule_occurrence(
            schedule_type,
            local_date=getattr(schedule, "local_date", None),
            local_time=schedule.local_time,
            weekdays=getattr(schedule, "weekdays", []) or [],
            timezone_name=schedule.timezone,
            at_or_before=current_time,
        )
        schedule.next_run_at = next_schedule_occurrence(
            schedule_type,
            local_date=getattr(schedule, "local_date", None),
            local_time=schedule.local_time,
            weekdays=getattr(schedule, "weekdays", []) or [],
            timezone_name=schedule.timezone,
            after=current_time,
        )
        run = ScheduleRun(
            schedule_id=schedule.schedule_id,
            scheduled_for=scheduled_for,
            task_id=None,
            trigger_result=ScheduleRunTriggerResult.BLOCKED.value,
        )
        try:
            task = self.task_service.create_for_schedule(
                TaskCreate(
                    target_device_id=schedule.target_device_id,
                    shop_ids=schedule.shop_ids,
                    skill_id=schedule.skill_id,
                    input=schedule.task_input_json,
                    parameter_preset_id=schedule.parameter_preset_id,
                ),
                team_id=schedule.team_id,
                created_by_user_id=schedule.created_by_user_id,
            )
            self.session.flush()
            run.task_id = task.task_id
            run.trigger_result = ScheduleRunTriggerResult.TASK_CREATED.value
        except AppError as error:
            run.trigger_error_code = error.code
            run.trigger_error_message = error.message

        self.repository.add_run(run)
        self.session.commit()
        self.session.refresh(run)
        return ScheduleTriggerSummary(
            run_id=run.run_id,
            schedule_id=run.schedule_id,
            scheduled_for=run.scheduled_for,
            trigger_result=ScheduleRunTriggerResult(run.trigger_result),
            task_id=run.task_id,
        )


def _task_create(
    *,
    target_device_id: UUID,
    shop_ids: list[UUID],
    execution_type: ScheduleExecutionType,
    application_id: str | None,
    parameter_preset_id: UUID | None,
    skill_id: str | None,
    parameters: dict[str, Any],
) -> TaskCreate:
    if execution_type is ScheduleExecutionType.BUSINESS_SKILL:
        if skill_id is None:
            raise TaskInputInvalidError("请选择业务 Skill")
        return TaskCreate(
            target_device_id=target_device_id,
            shop_ids=shop_ids,
            skill_id=skill_id,
            input=parameters,
        )
    if application_id is None:
        raise TaskInputInvalidError("请选择影刀应用")
    return TaskCreate(
        target_device_id=target_device_id,
        shop_ids=shop_ids,
        skill_id=TaskSkillId.YINGDAO_APP_RUN,
        input={"app_id": application_id, "params": parameters},
        parameter_preset_id=parameter_preset_id,
    )


def _schedule_to_read(record: ScheduleListRecord) -> ScheduleRead:
    schedule = record.schedule
    execution_type = _execution_type_for_skill(schedule.skill_id)
    return ScheduleRead(
        **_schedule_list_values(record),
        application_id=(
            str(schedule.task_input_json["app_id"])
            if execution_type is ScheduleExecutionType.YINGDAO_APPLICATION
            else None
        ),
        parameter_preset_id=schedule.parameter_preset_id,
        parameters=(
            dict(schedule.task_input_json.get("params", {}))
            if execution_type is ScheduleExecutionType.YINGDAO_APPLICATION
            else dict(schedule.task_input_json)
        ),
    )


def _schedule_to_list_item(record: ScheduleListRecord) -> ScheduleListItemRead:
    return ScheduleListItemRead(**_schedule_list_values(record))


def _schedule_list_values(record: ScheduleListRecord) -> dict[str, Any]:
    schedule = record.schedule
    return {
        "schedule_id": schedule.schedule_id,
        "name": schedule.name,
        "enabled": schedule.enabled,
        "target_device_id": schedule.target_device_id,
        "shop_ids": schedule.shop_ids,
        "device_display_name": record.device_display_name,
        "execution_type": _execution_type_for_skill(schedule.skill_id),
        "skill_id": schedule.skill_id,
        "execution_display_name": schedule.execution_display_name,
        "schedule_type": ScheduleType(schedule.schedule_type),
        "local_time": schedule.local_time,
        "timezone": schedule.timezone,
        "local_date": schedule.local_date,
        "weekdays": list(schedule.weekdays),
        "next_run_at": schedule.next_run_at,
        "latest_run": (
            _schedule_run_to_read(
                ScheduleRunRecord(record.latest_run, record.latest_task_status),
            )
            if record.latest_run is not None
            else None
        ),
        "created_at": schedule.created_at,
        "updated_at": schedule.updated_at,
    }


def _schedule_run_to_read(record: ScheduleRunRecord) -> ScheduleRunRead:
    run = record.run
    return ScheduleRunRead(
        run_id=run.run_id,
        schedule_id=run.schedule_id,
        scheduled_for=run.scheduled_for,
        task_id=run.task_id,
        task_status=(TaskStatus(record.task_status) if record.task_status else None),
        trigger_result=ScheduleRunTriggerResult(run.trigger_result),
        trigger_error_code=run.trigger_error_code,
        trigger_error_message=run.trigger_error_message,
        created_at=run.created_at,
    )


def _execution_type_for_skill(skill_id: str) -> ScheduleExecutionType:
    return (
        ScheduleExecutionType.YINGDAO_APPLICATION
        if skill_id == TaskSkillId.YINGDAO_APP_RUN
        else ScheduleExecutionType.BUSINESS_SKILL
    )
