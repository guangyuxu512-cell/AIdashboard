from sqlalchemy.orm import Session

from app.modules.automation_apps.models import AutomationApplicationConfig
from app.modules.automation_apps.repository import AutomationApplicationConfigRepository
from app.modules.automation_apps.schemas import (
    AutomationApplicationConfigRead,
    AutomationApplicationConfigUpsert,
)


class AutomationApplicationConfigService:
    def __init__(
        self,
        session: Session,
        repository: AutomationApplicationConfigRepository | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or AutomationApplicationConfigRepository(session)

    def get(
        self,
        provider_code: str,
        app_id: str,
    ) -> AutomationApplicationConfigRead | None:
        config = self.repository.get(provider_code, app_id)
        return self._to_read(config) if config is not None else None

    def upsert(
        self,
        provider_code: str,
        app_id: str,
        data: AutomationApplicationConfigUpsert,
    ) -> AutomationApplicationConfigRead:
        config = self.repository.get(provider_code, app_id)
        payload = data.input_schema.model_dump(mode="json")
        defaults = {
            field.name: field.default_value
            for field in data.input_schema.fields
            if field.default_value is not None
        }
        if config is None:
            config = AutomationApplicationConfig(
                provider_code=provider_code,
                app_id=app_id,
                schema_source="manual",
                input_schema=payload,
                default_values=defaults,
                version=1,
            )
            self.repository.add(config)
        else:
            config.input_schema = payload
            config.default_values = defaults
            config.schema_source = "manual"
            config.version += 1
        self.session.commit()
        self.session.refresh(config)
        return self._to_read(config)

    @staticmethod
    def _to_read(config: AutomationApplicationConfig) -> AutomationApplicationConfigRead:
        return AutomationApplicationConfigRead.model_validate(config, from_attributes=True)
