from typing import Protocol

from app.modules.authentication.contracts import (
    AuthProgress,
    DiscoveredShopIdentity,
    PlatformAuthContext,
    SessionSnapshot,
    VerificationChallenge,
    VerificationResponse,
)
from app.modules.credentials.enums import VerificationChannel
from app.modules.shops.enums import ShopPlatform


class VerificationProvider(Protocol):
    channel: VerificationChannel

    async def resolve(
        self,
        challenge: VerificationChallenge,
    ) -> VerificationResponse: ...


class PlatformAuthAdapter(Protocol):
    platform_code: ShopPlatform

    async def start_login(self, context: PlatformAuthContext) -> AuthProgress: ...

    async def detect_login_status(
        self,
        context: PlatformAuthContext,
    ) -> AuthProgress: ...

    async def submit_verification(
        self,
        context: PlatformAuthContext,
        response: VerificationResponse,
    ) -> AuthProgress: ...

    async def read_shop_identity(
        self,
        context: PlatformAuthContext,
    ) -> DiscoveredShopIdentity: ...

    async def capture_session(
        self,
        context: PlatformAuthContext,
    ) -> SessionSnapshot: ...
