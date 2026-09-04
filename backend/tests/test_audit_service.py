from __future__ import annotations

from typing import cast
from uuid import uuid4

from sqlalchemy.orm import Session

from app.modules.access.contracts import ActorContext
from app.modules.access.enums import DataScope
from app.modules.audit.enums import AuditAction, AuditTargetType
from app.modules.audit.models import AuditLog
from app.modules.audit.service import AuditLogService


class AuditLogRecorder:
    def __init__(self) -> None:
        self.records: list[AuditLog] = []

    def add(self, audit_log: AuditLog) -> None:
        self.records.append(audit_log)


def test_audit_service_normalizes_only_missing_details_to_an_object() -> None:
    recorder = AuditLogRecorder()
    actor = ActorContext(
        user_id=uuid4(),
        user_display_name="审计管理员",
        team_id=uuid4(),
        membership_id=uuid4(),
        role_code="access_admin",
        data_scope=DataScope.ALL,
    )
    service = AuditLogService(
        cast(Session, object()),
        repository=cast(object, recorder),
    )
    existing_details = {"changes": {"data_scope": {"from": "team", "to": "self"}}}

    service.record_access_management_action(
        request_id="request-empty-details",
        actor=actor,
        action=AuditAction.CREATE_TEAM,
        target_type=AuditTargetType.TEAM,
        target_id=uuid4(),
    )
    service.record_access_management_action(
        request_id="request-password-reset",
        actor=actor,
        action=AuditAction.RESET_MEMBER_PASSWORD,
        target_type=AuditTargetType.USER,
        target_id=uuid4(),
    )
    service.record_access_management_action(
        request_id="request-existing-details",
        actor=actor,
        action=AuditAction.UPDATE_MEMBERSHIP,
        target_type=AuditTargetType.MEMBERSHIP,
        target_id=uuid4(),
        details=existing_details,
    )

    assert recorder.records[0].details == {}
    assert recorder.records[1].details == {}
    assert recorder.records[2].details is existing_details
