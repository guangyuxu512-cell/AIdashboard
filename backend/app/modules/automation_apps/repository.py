from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.automation_apps.models import AutomationApplicationConfig


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
