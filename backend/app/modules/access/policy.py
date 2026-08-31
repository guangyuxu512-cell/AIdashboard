from typing import Any

from sqlalchemy.sql import ColumnElement, Select

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import InvalidDataScopeError


class DataScopePolicy:
    """Apply ownership predicates without knowing the concrete business entity."""

    @staticmethod
    def apply(
        statement: Select[Any],
        *,
        team_id_column: ColumnElement[Any],
        created_by_user_id_column: ColumnElement[Any],
        actor: ActorContext,
    ) -> Select[Any]:
        scope = actor.data_scope
        if not isinstance(scope, DataScope):
            raise InvalidDataScopeError()
        if scope is DataScope.SELF:
            return statement.where(
                team_id_column == actor.team_id,
                created_by_user_id_column == actor.user_id,
            )
        if scope is DataScope.TEAM:
            return statement.where(team_id_column == actor.team_id)
        if scope is DataScope.ALL:
            return statement
        raise InvalidDataScopeError()
