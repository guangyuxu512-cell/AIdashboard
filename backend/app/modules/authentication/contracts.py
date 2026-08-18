from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from app.modules.shops.enums import ShopPlatform


class VerificationChallengeType(str, Enum):
    SMS_CODE = "sms_code"
    EMAIL_CODE = "email_code"
    QR_SCAN = "qr_scan"
    APP_CONFIRM = "app_confirm"
    MANUAL = "manual"


class AuthProgressStatus(str, Enum):
    STARTED = "started"
    CHALLENGE_REQUIRED = "challenge_required"
    AUTHENTICATED = "authenticated"
    FAILED = "failed"


@dataclass(frozen=True)
class PlatformAuthContext:
    credential_id: UUID
    device_id: UUID
    shop_id: UUID | None = None


@dataclass(frozen=True)
class VerificationChallenge:
    challenge_id: UUID
    type: VerificationChallengeType
    prompt: str
    expires_at: datetime | None = None


@dataclass(frozen=True, repr=False)
class VerificationResponse:
    challenge_id: UUID
    value: str | None = None
    confirmed: bool = False


@dataclass(frozen=True)
class AuthProgress:
    status: AuthProgressStatus
    challenge: VerificationChallenge | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class DiscoveredShopIdentity:
    platform: ShopPlatform
    platform_shop_id: str
    display_name: str


@dataclass(frozen=True, repr=False)
class SessionSnapshot:
    payload: bytes
    captured_at: datetime
    validated_at: datetime | None = None
    expires_at: datetime | None = None
