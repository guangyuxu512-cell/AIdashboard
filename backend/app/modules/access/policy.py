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
        # The V2 product rule is intentionally smaller than the legacy
        # SELF/TEAM/ALL matrix: a super account can read every Team and a
        # normal member can read only its one effective Team.  Keeping this in
        # one predicate preserves SQL-side scope filtering before pagination.
        del created_by_user_id_column
        if actor.is_super_account:
            return statement
        return statement.where(team_id_column == actor.require_team_id())
