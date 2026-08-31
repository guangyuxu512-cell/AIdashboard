from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import column, select, table

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.access.exceptions import (
    HumanUserDisabledError,
    InvalidDataScopeError,
    TeamAccessDeniedError,
    TeamContextRequiredError,
    TeamMembershipRequiredError,
)
from app.modules.access.models import Team, TeamMembership
from app.modules.access.policy import DataScopePolicy
from app.modules.access.service import ActorContextService
from app.modules.users.models import User


class FakeUserRepository:
    def __init__(self, user: User | None) -> None:
        self.user = user

    def get(self, user_id: UUID) -> User | None:
        if self.user is None or self.user.user_id != user_id:
            return None
        return self.user


class FakeMembershipRepository:
    def __init__(
        self,
        memberships: list[tuple[TeamMembership, Team]],
    ) -> None:
        self.memberships = memberships

    def list_active_for_user(
        self,
        user_id: UUID,
    ) -> list[tuple[TeamMembership, Team]]:
        return [
            (membership, team)
            for membership, team in self.memberships
            if membership.user_id == user_id and membership.enabled and team.enabled
        ]

    def list_for_user(
        self,
        user_id: UUID,
    ) -> list[tuple[TeamMembership, Team]]:
        return [
            (membership, team)
            for membership, team in self.memberships
            if membership.user_id == user_id
        ]

    def get_for_user_and_team(
        self,
        *,
        user_id: UUID,
        team_id: UUID,
    ) -> tuple[TeamMembership, Team] | None:
        return next(
            (
                (membership, team)
                for membership, team in self.memberships
                if membership.user_id == user_id and team.team_id == team_id
            ),
            None,
        )


def membership_pair(
    user_id: UUID,
    *,
    enabled: bool = True,
    team_enabled: bool = True,
    scope: DataScope = DataScope.TEAM,
) -> tuple[TeamMembership, Team]:
    team_id = uuid4()
    return (
        TeamMembership(
            membership_id=uuid4(),
            team_id=team_id,
            user_id=user_id,
            role_code="member",
            data_scope=scope,
            enabled=enabled,
        ),
        Team(team_id=team_id, name=f"团队-{team_id}", enabled=team_enabled),
    )


def actor_service(
    user: User,
    memberships: list[tuple[TeamMembership, Team]],
) -> ActorContextService:
    return ActorContextService(
        cast(Any, None),
        membership_repository=cast(Any, FakeMembershipRepository(memberships)),
        user_repository=cast(Any, FakeUserRepository(user)),
    )


def test_actor_context_auto_selects_the_only_active_team() -> None:
    user = User(user_id=uuid4(), display_name="单团队用户", enabled=True)
    membership, team = membership_pair(user.user_id)

    actor = actor_service(user, [(membership, team)]).resolve(
        user_id=user.user_id,
        requested_team_id=None,
    )

    assert actor.user_id == user.user_id
    assert actor.team_id == team.team_id
    assert actor.membership_id == membership.membership_id
    assert actor.role_code == "member"
    assert actor.data_scope is DataScope.TEAM


def test_actor_context_selects_an_explicit_active_membership() -> None:
    user = User(user_id=uuid4(), display_name="多团队用户", enabled=True)
    first = membership_pair(user.user_id)
    second = membership_pair(user.user_id, scope=DataScope.SELF)

    actor = actor_service(user, [first, second]).resolve(
        user_id=user.user_id,
        requested_team_id=second[1].team_id,
    )

    assert actor.team_id == second[1].team_id
    assert actor.data_scope is DataScope.SELF


def test_actor_context_requires_selection_for_multiple_active_teams() -> None:
    user = User(user_id=uuid4(), display_name="多团队用户", enabled=True)
    service = actor_service(
        user,
        [membership_pair(user.user_id), membership_pair(user.user_id)],
    )

    with pytest.raises(TeamContextRequiredError):
        service.resolve(user_id=user.user_id, requested_team_id=None)


def test_actor_context_rejects_non_membership_and_disabled_membership() -> None:
    user = User(user_id=uuid4(), display_name="受限用户", enabled=True)
    disabled = membership_pair(user.user_id, enabled=False)
    service = actor_service(user, [disabled])

    with pytest.raises(TeamAccessDeniedError):
        service.resolve(
            user_id=user.user_id,
            requested_team_id=disabled[1].team_id,
        )
    with pytest.raises(TeamAccessDeniedError):
        service.resolve(user_id=user.user_id, requested_team_id=uuid4())


def test_actor_context_rejects_no_membership_and_disabled_user() -> None:
    user = User(user_id=uuid4(), display_name="无团队用户", enabled=True)
    service = actor_service(user, [])

    with pytest.raises(TeamMembershipRequiredError):
        service.resolve(user_id=user.user_id, requested_team_id=None)

    user.enabled = False
    with pytest.raises(HumanUserDisabledError):
        service.resolve(user_id=user.user_id, requested_team_id=None)


def make_actor(scope: object) -> ActorContext:
    return ActorContext(
        user_id=uuid4(),
        user_display_name="查询用户",
        team_id=uuid4(),
        membership_id=uuid4(),
        role_code="member",
        data_scope=cast(Any, scope),
    )


def test_data_scope_policy_applies_self_team_and_all_predicates() -> None:
    entities = table(
        "entities",
        column("entity_id"),
        column("team_id"),
        column("created_by_user_id"),
    )
    base = select(entities)

    self_statement = DataScopePolicy.apply(
        base,
        team_id_column=entities.c.team_id,
        created_by_user_id_column=entities.c.created_by_user_id,
        actor=make_actor(DataScope.SELF),
    )
    team_statement = DataScopePolicy.apply(
        base,
        team_id_column=entities.c.team_id,
        created_by_user_id_column=entities.c.created_by_user_id,
        actor=make_actor(DataScope.TEAM),
    )
    all_statement = DataScopePolicy.apply(
        base,
        team_id_column=entities.c.team_id,
        created_by_user_id_column=entities.c.created_by_user_id,
        actor=make_actor(DataScope.ALL),
    )

    assert str(self_statement.whereclause).count("entities.team_id") == 1
    assert str(self_statement.whereclause).count("entities.created_by_user_id") == 1
    assert str(team_statement.whereclause).count("entities.team_id") == 1
    assert "created_by_user_id" not in str(team_statement.whereclause)
    assert all_statement.whereclause is None


def test_data_scope_policy_fails_closed_for_an_untyped_or_unknown_scope() -> None:
    entities = table("entities", column("team_id"), column("created_by_user_id"))

    for invalid_scope in ("all", "unexpected", None):
        with pytest.raises(InvalidDataScopeError):
            DataScopePolicy.apply(
                select(entities),
                team_id_column=entities.c.team_id,
                created_by_user_id_column=entities.c.created_by_user_id,
                actor=make_actor(invalid_scope),
            )
