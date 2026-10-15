"""Existing source writes derive only a verified super account's saved Team."""

from dataclasses import replace
from uuid import UUID

from app.modules.product_selection.service import ProductSelectionFactService
from app.modules.product_selection.exceptions import SelectionObservationNotFoundError


def existing_source_context(facts: ProductSelectionFactService, actor, observation_id: UUID, *, execution=False, lock=False):
    current = facts._current_actor(actor)
    lookup = replace(current, team_id=None) if current.is_super_account else current
    row = facts.repository.get_for_actor(actor=lookup, observation_id=observation_id)
    if row is None:
        raise SelectionObservationNotFoundError()
    identity = facts.repository.candidate(row.candidate_id)
    if identity is None:
        raise SelectionObservationNotFoundError()
    if current.is_super_account:
        current = facts._current_actor(replace(current, team_id=identity.team_id))
    # Never use a row found with earlier super/Shop visibility after revalidation.
    row = facts.repository.get_for_actor(actor=current, observation_id=observation_id, lock=lock)
    if row is None or identity.team_id != current.require_team_id():
        raise SelectionObservationNotFoundError()
    if execution:
        facts._execution_shop(current, row.request_shop_id)
    return current, row, identity


def lock_candidate(facts, candidate_id):
    return facts.repository.lock_candidate(candidate_id)
