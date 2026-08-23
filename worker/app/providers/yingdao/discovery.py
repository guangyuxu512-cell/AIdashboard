import os
from datetime import UTC, datetime
from pathlib import Path

from app.providers.yingdao.applications import YingdaoApplicationAdapter
from app.providers.yingdao.contracts import YingdaoDiscoveryResult, YingdaoProviderStatus
from app.providers.yingdao.session import YingdaoSessionAdapter, YingdaoSessionError

class YingdaoDiscoveryService:
    def __init__(
        self,
        *,
        session_adapter: YingdaoSessionAdapter,
        application_adapter: YingdaoApplicationAdapter,
    ) -> None:
        self.session_adapter = session_adapter
        self.application_adapter = application_adapter
        self.data_root = Path(os.getenv("LOCALAPPDATA", ".")) / "ShadowBot"

    async def discover(self) -> YingdaoDiscoveryResult:
        discovered_at = datetime.now(UTC)
        try:
            session = await self.session_adapter.current(start_if_missing=True)
            applications = await self.application_adapter.list(session)
        except YingdaoSessionError as error:
            status = {
                "YINGDAO_NOT_INSTALLED": YingdaoProviderStatus.NOT_INSTALLED,
                "YINGDAO_VERSION_UNSUPPORTED": YingdaoProviderStatus.VERSION_UNSUPPORTED,
                "YINGDAO_NOT_LOGGED_IN": YingdaoProviderStatus.NEED_LOGIN,
            }.get(error.code, YingdaoProviderStatus.INTERFACE_UNREACHABLE)
            return YingdaoDiscoveryResult(
                provider_available=False,
                status=status,
                status_reason_code=error.code,
                status_reason=error.message,
                provider_version=error.provider_version,
                discovered_at=discovered_at,
            )
        account = session.account
        return YingdaoDiscoveryResult(
            provider_available=True,
            status=YingdaoProviderStatus.READY,
            provider_version=session.endpoint.process.version,
            execution_available=True,
            execution_version=session.endpoint.process.version,
            logged_in=True,
            account_display=account.display_name or account.user_name,
            account_type=account.account_type,
            enterprise_account=bool(account.enterprise_name),
            user_id=account.user_id,
            applications=applications,
            discovered_at=discovered_at,
        )
