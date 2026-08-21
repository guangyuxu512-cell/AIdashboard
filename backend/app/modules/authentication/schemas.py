from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.modules.credentials.enums import VerificationChannel
from app.modules.credentials.schemas import CredentialStatusRead
from app.modules.sessions.schemas import ShopSessionMetadataRead
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.schemas import ShopRead


class CompleteManagementOnboardingCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    platform: ShopPlatform
    platform_shop_id: str = Field(min_length=1, max_length=128)
    shop_display_name: str = Field(min_length=1, max_length=100)
    login_identifier: str = Field(min_length=1, max_length=320)
    secret: SecretStr = Field(min_length=1, max_length=1000)
    preferred_verification_channel: VerificationChannel = VerificationChannel.MANUAL
    session_payload_base64: SecretStr = Field(min_length=1)
    session_captured_at: datetime
    expected_version: Literal[0] = 0
    source: Literal["management_console"] = "management_console"


class ManagementOnboardingResult(BaseModel):
    shop: ShopRead
    credential: CredentialStatusRead
    session: ShopSessionMetadataRead
