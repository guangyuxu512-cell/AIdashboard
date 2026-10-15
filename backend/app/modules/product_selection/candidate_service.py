from datetime import UTC, datetime

from app.modules.audit.enums import AuditAction, AuditTargetType
from app.modules.audit.service import AuditLogService
from app.modules.product_selection.candidate_context import existing_source_context, lock_candidate
from app.modules.product_selection.service import ProductSelectionFactService


class SelectionCandidateService:
    def __init__(self, session):
        self.session = session
        self.facts = ProductSelectionFactService(session)

    def set_blocked(self, actor, observation_id, command, *, request_id):
        try:
            current, source, identity = existing_source_context(self.facts, actor, observation_id)
            identity = lock_candidate(self.facts, identity.candidate_id)
            current, source, visible_identity = existing_source_context(self.facts, current, observation_id)
            if identity.candidate_id != visible_identity.candidate_id:
                from app.modules.product_selection.exceptions import SelectionObservationNotFoundError
                raise SelectionObservationNotFoundError()
            if identity.blocked != command.blocked:
                before = identity.blocked
                identity.blocked = command.blocked
                identity.blocked_changed_at = identity.updated_at = datetime.now(UTC)
                identity.blocked_changed_by_user_id = current.user_id
                AuditLogService(self.session).record_access_management_action(
                    request_id=request_id, actor=current,
                    action=AuditAction.BLOCK_SELECTION_CANDIDATE if command.blocked else AuditAction.RESTORE_SELECTION_CANDIDATE,
                    target_type=AuditTargetType.SELECTION_CANDIDATE,
                    target_id=identity.candidate_id, details={"blocked_before": before, "blocked_after": command.blocked},
                )
            self.session.commit()
            return self.facts.get_read(actor=current, observation_id=observation_id)
        except Exception:
            self.session.rollback()
            raise
