from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.modules.credentials.enums import VerificationChannel
from app.modules.credentials.schemas import CredentialStatusRead
from app.modules.sessions.schemas import ShopSessionMetadataRead
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.schemas import ShopRead


class CompleteManagementOnboardingCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    platform: ShopPlatform
    platform_shop_id: str | None = Field(default=None, min_length=1, max_length=128)
    shop_display_name: str | None = Field(default=None, min_length=1, max_length=100)
    login_identifier: str = Field(min_length=1, max_length=320)
    secret: SecretStr = Field(min_length=1, max_length=1000)
    preferred_verification_channel: VerificationChannel = VerificationChannel.MANUAL
    session_payload_base64: SecretStr = Field(min_length=1)
    session_captured_at: datetime
    expected_version: Literal[0] = 0
    source: Literal["management_console"] = "management_console"

    @model_validator(mode="after")
    def validate_platform_identity_source(
        self,
    ) -> "CompleteManagementOnboardingCommand":
        if self.platform is ShopPlatform.DOUYIN:
            if not self.platform_shop_id or not self.shop_display_name:
                raise ValueError("抖店接入必须提供已识别的平台店铺身份")
        elif self.platform is ShopPlatform.PDD:
            if self.platform_shop_id is not None or self.shop_display_name is not None:
                raise ValueError("拼多多店铺身份必须由服务器平台接口识别")
        return self


class VerifyPddManagementLoginCommand(BaseModel):
    """Ephemeral PDD identity preflight; it never persists the session payload."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    session_payload_base64: SecretStr = Field(min_length=1)


class PddManagementLoginIdentityResult(BaseModel):
    platform_shop_id: str = Field(min_length=1, max_length=128)
    shop_display_name: str = Field(min_length=1, max_length=100)


class ManagementOnboardingResult(BaseModel):
    shop: ShopRead
    credential: CredentialStatusRead
    session: ShopSessionMetadataRead
