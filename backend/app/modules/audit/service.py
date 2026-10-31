from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.audit.enums import AuditAction, AuditTargetType
from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditLogRepository
from app.modules.audit.schemas import AuditLogRead
from app.shared.pagination import Page


class AuditLogService:
    def __init__(
        self,
        session: Session,
        repository: AuditLogRepository | None = None,
    ) -> None:
        self.repository = repository or AuditLogRepository(session)

    def record_worker_session_access(
        self, *, request_id: str, actor: ActorContext, shop_id: UUID,
        device_id: UUID, task_id: UUID, session_version: int,
    ) -> None:
        self.record_access_management_action(
            request_id=request_id,
            actor=actor,
            action=AuditAction.READ_TASK_SHOP_SESSION,
            target_type=AuditTargetType.SHOP,
            target_id=shop_id,
            details={
                "device_id": str(device_id),
                "task_id": str(task_id),
                "session_version": session_version,
            },
        )

    def record_access_management_action(
        self,
        *,
        request_id: str,
        actor: ActorContext,
        action: AuditAction,
        target_type: AuditTargetType,
        target_id: UUID,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.repository.add(
            AuditLog(
                request_id=request_id,
                actor_user_id=actor.user_id,
                team_id=actor.team_id,
                action=action.value,
                target_type=target_type.value,
                target_id=target_id,
                details={} if details is None else details,
            ),
        )

    def list_logs(
        self,
        *,
        page: int,
        page_size: int,
        created_from: datetime | None,
        created_to: datetime | None,
        actor_user_id: UUID | None,
        action: AuditAction | None,
    ) -> Page[AuditLogRead]:
        rows, total = self.repository.list(
            offset=(page - 1) * page_size,
            limit=page_size,
            created_from=created_from,
            created_to=created_to,
            actor_user_id=actor_user_id,
            action=action.value if action is not None else None,
        )
        return Page(
            items=[
                AuditLogRead(
                    audit_log_id=audit_log.audit_log_id,
                    request_id=audit_log.request_id,
                    actor_user_id=audit_log.actor_user_id,
                    actor_display_name=actor_display_name,
                    team_id=audit_log.team_id,
                    action=AuditAction(audit_log.action),
                    target_type=AuditTargetType(audit_log.target_type),
                    target_id=audit_log.target_id,
                    details=audit_log.details,
                    created_at=audit_log.created_at,
                )
                for audit_log, actor_display_name in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
        )
