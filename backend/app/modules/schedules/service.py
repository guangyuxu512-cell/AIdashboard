from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.modules.schedules.enums import (
    ScheduleExecutionType,
    ScheduleRunTriggerResult,
    ScheduleType,
)
from app.modules.schedules.exceptions import ScheduleNotFoundError
from app.modules.schedules.models import Schedule, ScheduleRun
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
    latest_daily_occurrence,
    next_daily_occurrence,
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
        *,
        now: datetime | None = None,
    ) -> ScheduleRead:
        current_time = now or datetime.now(UTC)
        task_data = _task_create(
            target_device_id=data.target_device_id,
            execution_type=data.execution_type,
            application_id=data.application_id,
            skill_id=data.skill_id,
            parameters=data.parameters,
        )
        prepared = self.task_service.prepare_scheduled_task(task_data)
        schedule = Schedule(
            name=data.name,
            enabled=data.enabled,
            target_device_id=data.target_device_id,
            skill_id=task_data.skill_id,
            execution_display_name=prepared.execution_display_name,
            schedule_type=data.schedule_type.value,
            local_time=data.local_time,
            timezone=data.timezone,
            task_input_json=prepared.input_json,
            next_run_at=(
                next_daily_occurrence(
                    data.local_time,
                    data.timezone,
                    after=current_time,
                )
                if data.enabled
                else None
            ),
        )
        self.repository.add(schedule)
        self.session.commit()
        self.session.refresh(schedule)
        return self.get(schedule.schedule_id)

    def update(
        self,
        schedule_id: UUID,
        data: ScheduleUpdate,
        *,
        now: datetime | None = None,
    ) -> ScheduleRead:
        current_time = now or datetime.now(UTC)
        schedule = self.repository.get_for_update(schedule_id)
        if schedule is None:
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
                existing_parameters = (
                    schedule.task_input_json.get("params", {})
                    if current_execution_type is execution_type
                    else {}
                )
            else:
                skill_id = values.get("skill_id")
                if skill_id is None and current_execution_type is execution_type:
                    skill_id = schedule.skill_id
                if skill_id is None:
                    raise TaskInputInvalidError("请选择业务 Skill")
                application_id = None
                existing_parameters = (
                    schedule.task_input_json
                    if current_execution_type is execution_type
                    else {}
                )
            parameters = values.get("parameters", existing_parameters)
            task_data = _task_create(
                target_device_id=target_device_id,
                execution_type=execution_type,
                application_id=application_id,
                skill_id=skill_id,
                parameters=parameters,
            )
            prepared = self.task_service.prepare_scheduled_task(task_data)

            schedule.name = values.get("name", schedule.name)
            schedule.target_device_id = target_device_id
            schedule.skill_id = task_data.skill_id
            schedule.execution_display_name = prepared.execution_display_name
            schedule.schedule_type = values.get(
                "schedule_type",
                ScheduleType(schedule.schedule_type),
            ).value
            schedule.local_time = values.get("local_time", schedule.local_time)
            schedule.timezone = values.get("timezone", schedule.timezone)
            schedule.task_input_json = prepared.input_json
            schedule.enabled = values.get("enabled", schedule.enabled)
            schedule.next_run_at = (
                next_daily_occurrence(
                    schedule.local_time,
                    schedule.timezone,
                    after=current_time,
                )
                if schedule.enabled
                else None
            )

        self.session.commit()
        return self.get(schedule_id)

    def archive(
        self,
        schedule_id: UUID,
        *,
        now: datetime | None = None,
    ) -> None:
        schedule = self.repository.get_for_update(schedule_id)
        if schedule is None:
            raise ScheduleNotFoundError()
        schedule.enabled = False
        schedule.next_run_at = None
        schedule.deleted_at = now or datetime.now(UTC)
        self.session.commit()

    def get(self, schedule_id: UUID) -> ScheduleRead:
        record = self.repository.get_record(schedule_id)
        if record is None:
            raise ScheduleNotFoundError()
        return _schedule_to_read(record)

    def list_management(
        self,
        *,
        page: int,
        page_size: int,
        enabled: bool | None,
        device_id: UUID | None,
        search: str | None,
    ) -> Page[ScheduleListItemRead]:
        normalized_search = search.strip() if search else None
        records, total = self.repository.list_management(
            offset=(page - 1) * page_size,
            limit=page_size,
            enabled=enabled,
            device_id=device_id,
            search=normalized_search or None,
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
        *,
        page: int,
        page_size: int,
    ) -> Page[ScheduleRunRead]:
        if self.repository.get_including_deleted(schedule_id) is None:
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

        scheduled_for = latest_daily_occurrence(
            schedule.local_time,
            schedule.timezone,
            at_or_before=current_time,
        )
        schedule.next_run_at = next_daily_occurrence(
            schedule.local_time,
            schedule.timezone,
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
                    skill_id=schedule.skill_id,
                    input=schedule.task_input_json,
                ),
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
    execution_type: ScheduleExecutionType,
    application_id: str | None,
    skill_id: str | None,
    parameters: dict[str, Any],
) -> TaskCreate:
    if execution_type is ScheduleExecutionType.BUSINESS_SKILL:
        if skill_id is None:
            raise TaskInputInvalidError("请选择业务 Skill")
        return TaskCreate(
            target_device_id=target_device_id,
            skill_id=skill_id,
            input=parameters,
        )
    if application_id is None:
        raise TaskInputInvalidError("请选择影刀应用")
    return TaskCreate(
        target_device_id=target_device_id,
        skill_id=TaskSkillId.YINGDAO_APP_RUN,
        input={"app_id": application_id, "params": parameters},
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
        "device_display_name": record.device_display_name,
        "execution_type": _execution_type_for_skill(schedule.skill_id),
        "skill_id": schedule.skill_id,
        "execution_display_name": schedule.execution_display_name,
        "schedule_type": ScheduleType(schedule.schedule_type),
        "local_time": schedule.local_time,
        "timezone": schedule.timezone,
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
