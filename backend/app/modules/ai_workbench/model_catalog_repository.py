from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.ai_workbench.models import AiModel


class AiModelRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_all(self) -> list[AiModel]:
        return list(
            self.session.scalars(
                select(AiModel).order_by(
                    AiModel.is_default.desc(),
                    AiModel.display_name.asc(),
                    AiModel.model_id.asc(),
                ),
            ),
        )

    def list_enabled(self) -> list[AiModel]:
        return list(
            self.session.scalars(
                select(AiModel)
                .where(AiModel.enabled.is_(True))
                .order_by(
                    AiModel.is_default.desc(),
                    AiModel.display_name.asc(),
                    AiModel.model_id.asc(),
                ),
            ),
        )

    def list_for_update(self) -> list[AiModel]:
        return list(
            self.session.scalars(
                select(AiModel)
                .order_by(AiModel.model_id.asc())
                .with_for_update(),
            ),
        )

    def get(self, model_id: UUID) -> AiModel | None:
        return self.session.get(AiModel, model_id)

    def add(self, model: AiModel) -> None:
        self.session.add(model)
