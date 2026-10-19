from typing import Any

from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlalchemy.sql import ColumnElement, Select

from app.modules.access.contracts import ActorContext


class DataScopePolicy:
    """Apply ownership predicates without knowing the concrete business entity."""

    @staticmethod
    def apply(
        statement: Select[Any],
        *,
        team_id_column: ColumnElement[Any] | InstrumentedAttribute[Any],
        created_by_user_id_column: ColumnElement[Any] | InstrumentedAttribute[Any],
        actor: ActorContext,
    ) -> Select[Any]:
        # Global super-account browsing has no Team. An explicit Team is both
        # the business view and write context, including the ordinary default
        # Team. Apply the same predicate before lists, counts and detail reads.
        del created_by_user_id_column
        if actor.is_super_account and actor.team_id is None:
            return statement
        return statement.where(team_id_column == actor.require_team_id())
