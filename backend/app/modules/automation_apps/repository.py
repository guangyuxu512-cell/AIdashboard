from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.policy import DataScopePolicy
from app.modules.automation_apps.models import AutomationApplicationConfig
from app.modules.automation_apps.models import AutomationParameterPreset


class AutomationApplicationConfigRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        provider_code: str,
        app_id: str,
    ) -> AutomationApplicationConfig | None:
        return self.session.scalar(
            select(AutomationApplicationConfig).where(
                AutomationApplicationConfig.provider_code == provider_code,
                AutomationApplicationConfig.app_id == app_id,
            ),
        )

    def add(self, config: AutomationApplicationConfig) -> None:
        self.session.add(config)


class AutomationParameterPresetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, preset: AutomationParameterPreset) -> None:
        self.session.add(preset)

    def list_for_actor(
        self,
        *,
        actor: ActorContext,
        app_id: str,
    ) -> list[AutomationParameterPreset]:
        statement = DataScopePolicy.apply(
            select(AutomationParameterPreset).where(
                AutomationParameterPreset.app_id == app_id,
            ),
            team_id_column=AutomationParameterPreset.team_id,
            created_by_user_id_column=AutomationParameterPreset.created_by_user_id,
            actor=actor,
        )
        return list(
            self.session.scalars(
                statement.order_by(
                    AutomationParameterPreset.name.asc(),
                    AutomationParameterPreset.preset_id.asc(),
                ),
            ),
        )

    def get_for_actor(
        self,
        *,
        actor: ActorContext,
        app_id: str,
        preset_id: object,
        for_update: bool = False,
    ) -> AutomationParameterPreset | None:
        statement = DataScopePolicy.apply(
            select(AutomationParameterPreset).where(
                AutomationParameterPreset.preset_id == preset_id,
                AutomationParameterPreset.app_id == app_id,
            ),
            team_id_column=AutomationParameterPreset.team_id,
            created_by_user_id_column=AutomationParameterPreset.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.with_for_update() if for_update else statement)

    def get_for_team(
        self,
        *,
        team_id: object,
        app_id: str,
        preset_id: object,
    ) -> AutomationParameterPreset | None:
        return self.session.scalar(
            select(AutomationParameterPreset).where(
                AutomationParameterPreset.preset_id == preset_id,
                AutomationParameterPreset.team_id == team_id,
                AutomationParameterPreset.app_id == app_id,
            ),
        )

    def list_all_for_actor(
        self,
        *,
        actor: ActorContext,
        app_id: str | None = None,
        name_query: str | None = None,
    ) -> list[AutomationParameterPreset]:
        statement = select(AutomationParameterPreset)
        if app_id is not None:
            statement = statement.where(AutomationParameterPreset.app_id == app_id)
        if name_query:
            statement = statement.where(
                AutomationParameterPreset.name.ilike(f"%{name_query}%"),
            )
        statement = DataScopePolicy.apply(
            statement,
            team_id_column=AutomationParameterPreset.team_id,
            created_by_user_id_column=AutomationParameterPreset.created_by_user_id,
            actor=actor,
        )
        return list(
            self.session.scalars(
                statement.order_by(
                    AutomationParameterPreset.updated_at.desc(),
                    AutomationParameterPreset.preset_id.asc(),
                ),
            ),
        )

    def exists_name(
        self,
        *,
        team_id: object,
        app_id: str,
        name: str,
        exclude_preset_id: object | None = None,
    ) -> bool:
        filters = [
            AutomationParameterPreset.team_id == team_id,
            AutomationParameterPreset.app_id == app_id,
            AutomationParameterPreset.name == name,
        ]
        if exclude_preset_id is not None:
            filters.append(AutomationParameterPreset.preset_id != exclude_preset_id)
        return bool(
            self.session.scalar(
                select(func.count())
                .select_from(AutomationParameterPreset)
                .where(*filters),
            ),
        )

    def reference_types(self, preset_id: object) -> tuple[str, ...]:
        """Return only the durable records that prevent removing a preset.

        Imports remain local because the automation app module owns the preset
        repository while Task and Schedule own their respective models.
        """
        from app.modules.schedules.models import Schedule
        from app.modules.tasks.models import Task

        references: list[str] = []
        if self.session.scalar(
            select(Task.task_id)
            .where(Task.parameter_preset_id == preset_id)
            .limit(1),
        ) is not None:
            references.append("task")
        if self.session.scalar(
            select(Schedule.schedule_id)
            .where(Schedule.parameter_preset_id == preset_id)
            .limit(1),
        ) is not None:
            references.append("schedule")
        return tuple(references)

    def remove(self, preset: AutomationParameterPreset) -> None:
        self.session.delete(preset)
