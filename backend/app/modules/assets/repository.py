from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.policy import DataScopePolicy
from app.modules.ai_workbench.models import (
    GenerationItem,
    GenerationItemAsset,
    MaterialGroupAsset,
)
from app.modules.assets.models import Asset
from app.modules.tasks.models import Task, TaskAsset


class AssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(
        self,
        *,
        actor: ActorContext,
        offset: int,
        limit: int,
        search: str | None,
    ) -> list[Asset]:
        statement = DataScopePolicy.apply(
            select(Asset),
            team_id_column=Asset.team_id,
            created_by_user_id_column=Asset.created_by_user_id,
            actor=actor,
        )
        if search:
            statement = statement.where(
                Asset.original_filename.ilike(f"%{search}%"),
            )
        return list(
            self.session.scalars(
                statement.order_by(
                    Asset.created_at.desc(),
                    Asset.asset_id.desc(),
                )
                .offset(offset)
                .limit(limit),
            ),
        )

    def count(self, *, actor: ActorContext, search: str | None) -> int:
        statement = DataScopePolicy.apply(
            select(func.count()).select_from(Asset),
            team_id_column=Asset.team_id,
            created_by_user_id_column=Asset.created_by_user_id,
            actor=actor,
        )
        if search:
            statement = statement.where(
                Asset.original_filename.ilike(f"%{search}%"),
            )
        return int(
            self.session.scalar(statement) or 0,
        )

    def get_for_actor(
        self,
        *,
        actor: ActorContext,
        asset_id: UUID,
    ) -> Asset | None:
        statement = DataScopePolicy.apply(
            select(Asset).where(Asset.asset_id == asset_id),
            team_id_column=Asset.team_id,
            created_by_user_id_column=Asset.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement)

    def get_for_actor_for_update(
        self,
        *,
        actor: ActorContext,
        asset_id: UUID,
    ) -> Asset | None:
        statement = DataScopePolicy.apply(
            select(Asset).where(Asset.asset_id == asset_id),
            team_id_column=Asset.team_id,
            created_by_user_id_column=Asset.created_by_user_id,
            actor=actor,
        )
        return self.session.scalar(statement.with_for_update())

    def list_by_ids_for_actor(
        self,
        *,
        actor: ActorContext,
        asset_ids: Sequence[UUID],
    ) -> Sequence[Asset]:
        if not asset_ids:
            return []
        statement = DataScopePolicy.apply(
            select(Asset).where(Asset.asset_id.in_(asset_ids)),
            team_id_column=Asset.team_id,
            created_by_user_id_column=Asset.created_by_user_id,
            actor=actor,
        )
        return list(self.session.scalars(statement))

    def list_by_ids_for_actor_for_update(
        self,
        *,
        actor: ActorContext,
        asset_ids: Sequence[UUID],
    ) -> Sequence[Asset]:
        if not asset_ids:
            return []
        statement = DataScopePolicy.apply(
            select(Asset).where(Asset.asset_id.in_(asset_ids)),
            team_id_column=Asset.team_id,
            created_by_user_id_column=Asset.created_by_user_id,
            actor=actor,
        )
        return list(self.session.scalars(statement.with_for_update()))

    def list_by_ids(self, asset_ids: Sequence[UUID]) -> Sequence[Asset]:
        if not asset_ids:
            return []
        return list(
            self.session.scalars(select(Asset).where(Asset.asset_id.in_(asset_ids))),
        )

    def get_for_worker_task(
        self,
        *,
        task_id: UUID,
        device_id: UUID,
        asset_id: UUID,
    ) -> Asset | None:
        return self.session.scalar(
            select(Asset)
            .join(TaskAsset, TaskAsset.asset_id == Asset.asset_id)
            .join(Task, Task.task_id == TaskAsset.task_id)
            .where(
                Task.task_id == task_id,
                Task.target_device_id == device_id,
                Task.status == "running",
                TaskAsset.asset_id == asset_id,
            ),
        )

    def is_referenced(self, asset_id: UUID) -> bool:
        reference_columns = (
            TaskAsset.asset_id,
            MaterialGroupAsset.asset_id,
            GenerationItemAsset.asset_id,
            GenerationItem.output_asset_id,
        )
        return any(
            self.session.scalar(
                select(column).where(column == asset_id).limit(1),
            )
            is not None
            for column in reference_columns
        )

    def add(self, asset: Asset) -> None:
        self.session.add(asset)

    def delete(self, asset: Asset) -> None:
        self.session.delete(asset)
