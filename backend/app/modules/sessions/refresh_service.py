import base64
import json
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import SecretCipher
from app.modules.sessions.auth_context import StoredManagementSessionPayload
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.exceptions import (
    SessionRefreshLeaseConflictError,
    SessionRefreshLeaseInvalidError,
    SessionVersionConflictError,
    ShopSessionNotConfiguredError,
    ShopSessionPayloadInvalidError,
)
from app.modules.sessions.health_service import ShopSessionHealthService
from app.modules.sessions.repository import ShopSessionRepository
from app.modules.sessions.schemas import (
    CompleteShopSessionRefreshCommand,
    ShopSessionHealthRead,
    ShopSessionRefreshLeaseRead,
    StoreShopSessionCommand,
)
from app.modules.sessions.service import ShopSessionService
from app.modules.operating_dashboard.service import OperatingDashboardService
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.repository import ShopRepository

logger = logging.getLogger(__name__)

_REFRESH_STAGES = frozenset({
    "candidate_encoding", "candidate_json", "candidate_schema",
    "candidate_platform", "candidate_identity", "candidate_validation", "target_changed",
})
_VALIDATION_STEPS = frozenset({
    "context_validation", "identity_connector", "cookie_merge", "unclassified",
})
_IDENTITY_FIELDS = {
    "platform": "platform",
    "platformShopId": "platform_shop_id", "platform_shop_id": "platform_shop_id",
    "shopDisplayName": "shop_display_name", "shop_display_name": "shop_display_name",
}
_COOKIE_FIELDS = {
    "name": "name", "value": "value", "domain": "domain", "path": "path",
    "secure": "secure", "httpOnly": "http_only", "http_only": "http_only",
    "sameSite": "same_site", "same_site": "same_site",
    "expirationDate": "expiration_date", "expiration_date": "expiration_date",
}
_SCHEMA_FIELDS = frozenset({
    "document", "schema", "platform", "identity", "cookies", "cookies.item", "unknown",
    *(f"identity.{field}" for field in _IDENTITY_FIELDS.values()),
    *(f"cookies.{field}" for field in _COOKIE_FIELDS.values()),
})
_SCHEMA_ERROR_TYPES = frozenset({
    "missing", "model_type", "list_type", "string_type", "string_too_short",
    "too_short", "enum", "literal_error", "bool_type", "bool_parsing",
    "float_type", "float_parsing", "finite_number", "other",
})


def _schema_field(location: object) -> str:
    # Never expose raw locations, array indices or caller-provided field names.
    if not isinstance(location, tuple):
        return "unknown"
    if not location:
        return "document"
    root = location[0]
    if len(location) == 1:
        if not isinstance(root, str):
            return "unknown"
        return {
            "schema": "schema", "schema_name": "schema", "platform": "platform",
            "identity": "identity", "cookies": "cookies",
        }.get(root, "unknown")
    if root == "identity" and len(location) == 2 and isinstance(location[1], str):
        field = _IDENTITY_FIELDS.get(location[1])
        return f"identity.{field}" if field else "unknown"
    if root == "cookies" and type(location[1]) is int:
        if len(location) == 2:
            return "cookies.item"
        if len(location) == 3 and isinstance(location[2], str):
            field = _COOKIE_FIELDS.get(location[2])
            return f"cookies.{field}" if field else "unknown"
    return "unknown"


def _safe_schema_issue(item: object) -> dict[str, str]:
    fields = item if isinstance(item, Mapping) else {}
    field, reason = fields.get("field"), fields.get("type")
    return {
        "field": (
            field if isinstance(field, str) and field in _SCHEMA_FIELDS else "unknown"
        ),
        "type": (
            reason if isinstance(reason, str) and reason in _SCHEMA_ERROR_TYPES else "other"
        ),
    }


def _schema_failure_details(error: ValidationError) -> dict[str, object]:
    issues: list[dict[str, str]] = []
    truncated = False
    for item in error.errors(include_input=False, include_context=False, include_url=False):
        issue = _safe_schema_issue({
            "field": _schema_field(item.get("loc")), "type": item.get("type"),
        })
        if issue in issues:
            continue
        if len(issues) == 3:
            truncated = True
            break
        issues.append(issue)
    return {
        "refresh_stage": "candidate_schema",
        "schema_issues": issues,
        "schema_issues_truncated": truncated,
    }


def safe_refresh_diagnostic_details(
    error: ShopSessionPayloadInvalidError,
) -> dict[str, object]:
    """Project only this refresh diagnostic's bounded constants, never arbitrary details."""
    details = error.details if isinstance(error.details, Mapping) else {}
    stage = details.get("refresh_stage")
    safe: dict[str, object] = {
        "refresh_stage": (
            stage if isinstance(stage, str) and stage in _REFRESH_STAGES else "unclassified"
        ),
    }
    if safe["refresh_stage"] == "candidate_validation":
        step = details.get("validation_step")
        safe["validation_step"] = (
            step if isinstance(step, str) and step in _VALIDATION_STEPS else "unclassified"
        )
    elif safe["refresh_stage"] == "candidate_schema":
        items = details.get("schema_issues")
        if isinstance(items, list):
            issues: list[dict[str, str]] = []
            for item in items[:3]:
                issue = _safe_schema_issue(item)
                if issue not in issues:
                    issues.append(issue)
            safe["schema_issues"] = issues
            safe["schema_issues_truncated"] = (
                len(items) > 3 or details.get("schema_issues_truncated") is True
            )
        else:
            safe["schema_issues"] = [{"field": "unknown", "type": "other"}]
            safe["schema_issues_truncated"] = False
    return safe


class ShopSessionRefreshService:
    def __init__(
        self,
        session: Session,
        cipher: SecretCipher,
        health_service: ShopSessionHealthService,
        *,
        repository: ShopSessionRepository | None = None,
        shop_repository: ShopRepository | None = None,
        session_service: ShopSessionService | None = None,
        collection_resume: Callable[[UUID], int] | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.repository = repository or ShopSessionRepository(session)
        self.shop_repository = shop_repository or ShopRepository(session)
        self.session_service = session_service or ShopSessionService(session, cipher)
        self.collection_resume = collection_resume or (
            lambda shop_id: OperatingDashboardService(
                self.session,
            ).resume_after_session_refresh(shop_id)
        )
        self.health_service = health_service
        self.settings = settings or get_settings()

    def acquire(self, shop_id: UUID) -> ShopSessionRefreshLeaseRead:
        if self.shop_repository.get(shop_id) is None:
            raise ShopNotFoundError()
        now = datetime.now(UTC)
        if self.repository.get_by_shop(shop_id) is None:
            self.session_service.reserve_for_refresh(shop_id, now)
        lease_id = uuid4()
        expires_at = now + timedelta(
            seconds=self.settings.shop_session_refresh_lease_seconds,
        )
        if not self.repository.acquire_refresh_lease(
            shop_id=shop_id,
            lease_id=lease_id,
            now=now,
            expires_at=expires_at,
        ):
            self.session.rollback()
            raise SessionRefreshLeaseConflictError()
        self.session.commit()
        current = self.repository.get_by_shop(shop_id)
        if current is None:
            raise ShopSessionNotConfiguredError()
        return ShopSessionRefreshLeaseRead(
            shop_id=shop_id,
            lease_id=lease_id,
            expected_version=current.version,
            expires_at=expires_at,
        )

    def release(self, shop_id: UUID, lease_id: UUID) -> None:
        self.repository.release_refresh_lease(shop_id=shop_id, lease_id=lease_id)
        self.session.commit()

    def complete(
        self,
        shop_id: UUID,
        command: CompleteShopSessionRefreshCommand,
        *,
        recheck_authorization: Callable[[], None] | None = None,
    ) -> ShopSessionHealthRead:
        now = datetime.now(UTC)
        if not self.repository.has_active_refresh_lease(
            shop_id=shop_id,
            lease_id=command.lease_id,
            now=now,
        ):
            raise SessionRefreshLeaseInvalidError()
        try:
            return self._complete_under_lease(shop_id, command, recheck_authorization)
        finally:
            # A failed write must not leave the transaction unusable for release.
            self.session.rollback()
            try:
                self.release(shop_id, command.lease_id)
            except Exception:
                self.session.rollback()
                # A successful CAS already clears the lease atomically. Failed
                # attempts also have the existing timeout recovery boundary.
                logger.warning("Session refresh lease release incomplete")

    def _complete_under_lease(
        self,
        shop_id: UUID,
        command: CompleteShopSessionRefreshCommand,
        recheck_authorization: Callable[[], None] | None,
    ) -> ShopSessionHealthRead:
        stored = self.repository.get_by_shop(shop_id)
        shop = self.shop_repository.get(shop_id)
        if stored is None:
            raise ShopSessionNotConfiguredError()
        if shop is None:
            raise ShopNotFoundError()
        if stored.version != command.expected_version:
            raise SessionVersionConflictError()

        try:
            payload = base64.b64decode(
                command.session_payload_base64.get_secret_value(),
                validate=True,
            )
        except ValueError:
            raise ShopSessionPayloadInvalidError(
                details={"refresh_stage": "candidate_encoding"},
            ) from None
        try:
            document = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ShopSessionPayloadInvalidError(
                details={"refresh_stage": "candidate_json"},
            ) from None
        try:
            parsed = StoredManagementSessionPayload.model_validate(
                document,
            )
        except ValidationError as error:
            raise ShopSessionPayloadInvalidError(
                details=_schema_failure_details(error),
            ) from None
        if parsed.platform is not shop.platform:
            raise ShopSessionPayloadInvalidError(
                details={"refresh_stage": "candidate_platform"},
            )
        if (
            parsed.identity is not None
            and shop.platform_shop_id is not None
            and parsed.identity.platform_shop_id != shop.platform_shop_id
        ):
            raise ShopSessionPayloadInvalidError(
                "登录身份与目标店铺不匹配", details={"refresh_stage": "candidate_identity"},
            )

        platform = shop.platform
        platform_shop_id = shop.platform_shop_id
        source_device_id = stored.source_device_id
        expires_at = stored.expires_at
        # No transaction/row lock stays open during platform I/O. Nothing has
        # been changed yet; a failed candidate preserves every old Session field.
        self.session.rollback()
        try:
            candidate = self.health_service.validate_candidate(
                shop_id, platform, platform_shop_id, command.expected_version, payload, parsed,
            )
        except ShopSessionPayloadInvalidError as error:
            safe = safe_refresh_diagnostic_details(error)
            error.details = {
                "refresh_stage": "candidate_validation",
                "validation_step": safe.get("validation_step", "unclassified"),
            }
            raise
        if recheck_authorization is not None:
            recheck_authorization()
        shop = self.shop_repository.get(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        if shop.platform is not platform or shop.platform_shop_id != platform_shop_id:
            raise ShopSessionPayloadInvalidError(
                "目标店铺身份已改变，请重新登录", details={"refresh_stage": "target_changed"},
            )
        metadata = self.session_service.store_payload(
            StoreShopSessionCommand(
                shop_id=shop_id,
                expected_version=command.expected_version,
                status=ShopSessionStatus.VALID,
                source_device_id=source_device_id,
                captured_at=command.captured_at,
                validated_at=candidate.validated_at,
                expires_at=expires_at,
            ),
            candidate.payload,
            refresh_lease_id=command.lease_id,
        )
        try:
            self.collection_resume(shop_id)
        except Exception:
            self.session.rollback()
            # The Session has already committed. A queue error must never make
            # the client resubmit a valid capture or misreport authentication.
            logger.warning("Session updated; paused collection resume incomplete")
        return ShopSessionHealthRead(
            shop_id=shop_id,
            platform=platform,
            platform_shop_id=candidate.platform_shop_id,
            shop_display_name=candidate.shop_display_name,
            status=metadata.status,
            version=metadata.version,
            validated_at=candidate.validated_at,
            used_cached_validation=False,
            cookie_updates_applied=candidate.cookie_updates_applied,
        )
