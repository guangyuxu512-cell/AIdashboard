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
        team_id: object | None,
        app_id: str | None = None,
        app_ids: tuple[str, ...] | None = None,
        name_query: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> list[AutomationParameterPreset]:
        statement = self._list_all_for_actor_statement(
            actor=actor,
            team_id=team_id,
            app_id=app_id,
            app_ids=app_ids,
            name_query=name_query,
        ).order_by(
            AutomationParameterPreset.updated_at.desc(),
            AutomationParameterPreset.preset_id.asc(),
        )
        if limit is not None:
            statement = statement.offset(offset).limit(limit)
        return list(self.session.scalars(statement))

    def count_all_for_actor(
        self,
        *,
        actor: ActorContext,
        team_id: object | None,
        app_id: str | None = None,
        app_ids: tuple[str, ...] | None = None,
        name_query: str | None = None,
    ) -> int:
        statement = self._list_all_for_actor_statement(
            actor=actor,
            team_id=team_id,
            app_id=app_id,
            app_ids=app_ids,
            name_query=name_query,
        )
        count_statement = statement.with_only_columns(func.count()).order_by(None)
        return int(self.session.scalar(count_statement) or 0)

    @staticmethod
    def _list_all_for_actor_statement(
        *,
        actor: ActorContext,
        team_id: object | None,
        app_id: str | None,
        app_ids: tuple[str, ...] | None,
        name_query: str | None,
    ):
        statement = select(AutomationParameterPreset)
        if app_id is not None:
            statement = statement.where(AutomationParameterPreset.app_id == app_id)
        if app_ids is not None:
            statement = statement.where(AutomationParameterPreset.app_id.in_(app_ids))
        if name_query:
            statement = statement.where(
                AutomationParameterPreset.name.ilike(f"%{name_query}%"),
            )
        # DataScopePolicy applies the normal member's Team predicate in SQL.
        # A super account with no selected Team is intentionally allowed to
        # read across Teams; an explicit selected Team narrows the same SQL
        # collection.  This keeps total, ordering and page contents aligned.
        statement = DataScopePolicy.apply(
            statement,
            team_id_column=AutomationParameterPreset.team_id,
            created_by_user_id_column=AutomationParameterPreset.created_by_user_id,
            actor=actor,
        )
        if team_id is not None:
            statement = statement.where(AutomationParameterPreset.team_id == team_id)
        return statement

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
