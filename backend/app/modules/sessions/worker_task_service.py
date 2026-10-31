from datetime import UTC, datetime
from hmac import compare_digest
from uuid import UUID

from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import SecretCipher
from app.modules.access.module_access import ModuleCode
from app.modules.access.exceptions import TeamResourceAccessDeniedError
from app.modules.access.repository import ExecutionAuthorizationLockRepository
from app.modules.access.service import (
    ActorContextService,
    ModuleAccessService,
    TeamAuthorizationService,
)
from app.modules.audit.service import AuditLogService
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.sessions.exceptions import (
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
    ShopSessionReadBusyError,
)
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.sessions.worker_task_contract import (
    WorkerTaskSessionCookie,
    WorkerTaskSessionRead,
)
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.repository import ShopDeviceBindingRepository, ShopRepository
from app.modules.tasks.exceptions import TaskNotFoundError
from app.modules.tasks.precheck_contract import PRODUCT_PRECHECK_SKILL_ID
from app.modules.tasks.repository import TaskRepository
from app.modules.workers.exceptions import WorkerAuthenticationError
from app.modules.workers.repository import WorkerRepository
from app.modules.workers.service import WorkerPrincipal


class WorkerTaskSessionService:
    """Release a single shop's minimum session only to its live precheck task."""

    def __init__(
        self,
        session: Session,
        cipher: SecretCipher,
        *,
        settings: Settings | None = None,
        task_repository: TaskRepository | None = None,
        shop_repository: ShopRepository | None = None,
        binding_repository: ShopDeviceBindingRepository | None = None,
        session_repository: ShopSessionRepository | None = None,
        accessor: ShopSessionAccessor | None = None,
        actor_service: ActorContextService | None = None,
        module_service: ModuleAccessService | None = None,
        team_service: TeamAuthorizationService | None = None,
        authorization_locks: ExecutionAuthorizationLockRepository | None = None,
        audit_service: AuditLogService | None = None,
        worker_repository: WorkerRepository | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.tasks = task_repository or TaskRepository(session)
        self.shops = shop_repository or ShopRepository(session)
        self.bindings = binding_repository or ShopDeviceBindingRepository(session)
        self.sessions = session_repository or ShopSessionRepository(session)
        self.accessor = accessor or ShopSessionAccessor(session, cipher, self.sessions)
        self.actors = actor_service or ActorContextService(session)
        self.modules = module_service or ModuleAccessService(session)
        self.teams = team_service or TeamAuthorizationService(session)
        self.authorization_locks = authorization_locks or ExecutionAuthorizationLockRepository(session)
        self.audit = audit_service or AuditLogService(session)
        self.worker_credentials = worker_repository or WorkerRepository(session)

    def read(
        self, principal: WorkerPrincipal, *, task_id: UUID, shop_id: UUID,
        request_id: str, now: datetime | None = None,
    ) -> WorkerTaskSessionRead:
        if not self.settings.worker_precheck_session_access_enabled:
            raise TaskNotFoundError()
        try:
            self.authorization_locks.set_lock_timeout()
            return self._read_locked(
                principal, task_id=task_id, shop_id=shop_id,
                request_id=request_id, now=now,
            )
        except DBAPIError as error:
            if getattr(error.orig, "sqlstate", None) != "55P03":
                raise
            self.session.rollback()
            raise ShopSessionReadBusyError() from None

    def _read_locked(
        self, principal: WorkerPrincipal, *, task_id: UUID, shop_id: UUID,
        request_id: str, now: datetime | None,
    ) -> WorkerTaskSessionRead:
        checked_at = now or datetime.now(UTC)
        if self.tasks.get_enabled_device_for_session_read(principal.device_id) is None:
            raise TaskNotFoundError()
        credential = self.worker_credentials.get_credential_for_session_read(principal.device_id)
        if (
            principal.credential_hash is None
            or credential is None
            or not credential.enabled
            or not compare_digest(principal.credential_hash, credential.token_hash)
        ):
            raise WorkerAuthenticationError()
        task = self.tasks.get_running_for_device_for_session_read(
            task_id=task_id, device_id=principal.device_id, now=checked_at,
        )
        if (
            task is None
            or task.skill_id != PRODUCT_PRECHECK_SKILL_ID
            or task.created_by_user_id is None
            or task.lease_until is None
        ):
            raise TaskNotFoundError()

        if not self.tasks.lock_shop_for_session_read(task_id=task_id, shop_id=shop_id):
            raise TaskNotFoundError()
        locked = self.authorization_locks.lock(
            user_id=task.created_by_user_id,
            team_id=task.team_id,
            device_id=principal.device_id,
            shop_id=shop_id,
        )
        if not locked.user or not locked.team:
            raise TaskNotFoundError()
        if not locked.device or not locked.shop:
            raise TeamResourceAccessDeniedError()
        actor = self.actors.resolve(
            user_id=task.created_by_user_id, requested_team_id=task.team_id,
        )
        if not actor.is_super_account and (not locked.membership or not locked.module):
            raise TeamResourceAccessDeniedError()
        self.modules.require_module_access(actor, ModuleCode.TASK)
        self.teams.require_execution_resources(
            team_id=task.team_id, device_id=principal.device_id, shop_ids=[shop_id],
        )
        shop = self.shops.get_for_session_read(shop_id)
        binding = self.bindings.get_for_session_read(shop_id, principal.device_id)
        if (
            shop is None
            or not shop.enabled
            or shop.platform != ShopPlatform.DOUYIN
            or binding is None
            or not binding.enabled
        ):
            raise TaskNotFoundError()
        stored = self.sessions.get_by_shop_for_session_read(shop_id)
        if stored is None:
            raise ShopSessionNotConfiguredError()
        # A lock wait may have lasted longer than the task's remaining lease.
        # Never make the authorization decision using only the pre-lock clock.
        checked_at = now or datetime.now(UTC)
        if task.lease_until <= checked_at:
            raise TaskNotFoundError()
        # Existing central policy treats expires_at as a warning, not proof of
        # invalid authentication. The platform response remains authoritative.
        context = self.accessor.get_auth_context(shop_id, ShopPlatform.DOUYIN)
        # A precheck must never receive an ambiguous or different store's session.
        if (
            context.identity is None
            or not shop.platform_shop_id
            or context.identity.platform is not ShopPlatform.DOUYIN
            or context.identity.platform_shop_id != shop.platform_shop_id
        ):
            raise ShopSessionPayloadInvalidError()

        result = WorkerTaskSessionRead(
            shop_id=shop_id,
            platform=context.platform,
            session_version=context.session_version,
            task_lease_until=task.lease_until,
            cookies=tuple(
                WorkerTaskSessionCookie.model_validate(cookie.model_dump())
                for cookie in context.cookies
            ),
        )
        self.audit.record_worker_session_access(
            request_id=request_id,
            actor=actor,
            shop_id=shop_id,
            device_id=principal.device_id,
            task_id=task_id,
            session_version=context.session_version,
        )
        # The credential must not be returned if the audit record cannot commit.
        self.session.commit()
        # A slow audit commit may have consumed the remaining lease. The audit
        # remains as a record of the authorized read even when delivery fails.
        if result.task_lease_until <= (now or datetime.now(UTC)):
            raise TaskNotFoundError()
        return result
