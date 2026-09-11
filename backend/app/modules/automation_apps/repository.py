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
