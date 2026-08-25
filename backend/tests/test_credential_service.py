from datetime import UTC, datetime
from uuid import UUID, uuid4

from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.security import SecretCipher
from app.modules.credentials.enums import VerificationChannel
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.credentials.schemas import CredentialCreate, CredentialUpdate
from app.modules.credentials.service import CredentialService
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from tests.support import FakeSession


class FakeCredentialRepository:
    def __init__(self) -> None:
        self.items: dict[UUID, PlatformCredential] = {}

    def get(self, credential_id: UUID) -> PlatformCredential | None:
        return self.items.get(credential_id)

    def add(self, credential: PlatformCredential) -> None:
        credential.credential_id = uuid4()
        credential.created_at = datetime.now(UTC)
        credential.updated_at = credential.created_at
        self.items[credential.credential_id] = credential


class FakeBindingRepository:
    def __init__(
        self,
        credentials: FakeCredentialRepository,
    ) -> None:
        self.credentials = credentials
        self.items: dict[tuple[UUID, UUID], ShopCredentialBinding] = {}

    def get(self, shop_id: UUID, credential_id: UUID) -> ShopCredentialBinding | None:
        return self.items.get((shop_id, credential_id))

    def get_active_by_shop(
        self,
        shop_id: UUID,
    ) -> tuple[ShopCredentialBinding, PlatformCredential] | None:
        for binding in self.items.values():
            credential = self.credentials.get(binding.credential_id)
            if (
                binding.shop_id == shop_id
                and binding.enabled
                and credential is not None
                and credential.enabled
            ):
                return binding, credential
        return None

    def get_latest_by_shop(
        self,
        shop_id: UUID,
    ) -> tuple[ShopCredentialBinding, PlatformCredential] | None:
        matches = [item for item in self.items.values() if item.shop_id == shop_id]
        if not matches:
            return None
        binding = matches[-1]
        return binding, self.credentials.items[binding.credential_id]

    def list_by_credential(self, credential_id: UUID) -> list[ShopCredentialBinding]:
        return [
            binding
            for binding in self.items.values()
            if binding.credential_id == credential_id
        ]

    def add(self, binding: ShopCredentialBinding) -> None:
        binding.created_at = datetime.now(UTC)
        binding.updated_at = binding.created_at
        self.items[(binding.shop_id, binding.credential_id)] = binding


class FakeShopRepository:
    def __init__(self, shops: dict[UUID, Shop]) -> None:
        self.shops = shops

    def get(self, shop_id: UUID) -> Shop | None:
        return self.shops.get(shop_id)


def test_credential_encrypts_updates_and_can_bind_multiple_shops() -> None:
    session = FakeSession()
    cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
    first_shop_id = uuid4()
    second_shop_id = uuid4()
    shops = {
        shop_id: Shop(
            shop_id=shop_id,
            display_name=f"店铺-{index}",
            platform=ShopPlatform.DOUYIN,
            enabled=True,
        )
        for index, shop_id in enumerate((first_shop_id, second_shop_id), start=1)
    }
    credentials = FakeCredentialRepository()
    bindings = FakeBindingRepository(credentials)
    service = CredentialService(
        session,  # type: ignore[arg-type]
        cipher,
        credentials,  # type: ignore[arg-type]
        bindings,  # type: ignore[arg-type]
        FakeShopRepository(shops),  # type: ignore[arg-type]
    )

    status = service.create(
        CredentialCreate(
            shop_id=first_shop_id,
            login_identifier="13812348888",
            secret=SecretStr("original-password"),
            preferred_verification_channel=VerificationChannel.MANUAL,
        ),
    )
    credential = credentials.items[status.credential_id]  # type: ignore[index]

    assert b"original-password" not in credential.secret_encrypted
    assert cipher.decrypt_text(credential.secret_encrypted) == "original-password"
    assert status.masked_identifier == "138****8888"

    original_encrypted = credential.secret_encrypted
    service.update(
        credential.credential_id,
        CredentialUpdate(secret=""),
    )
    assert credential.secret_encrypted == original_encrypted

    service.update(
        credential.credential_id,
        CredentialUpdate(login_identifier="new-user", secret=""),
    )
    assert credential.secret_encrypted == original_encrypted

    service.update(
        credential.credential_id,
        CredentialUpdate(secret=SecretStr("updated-password")),
    )
    assert cipher.decrypt_text(credential.secret_encrypted) == "updated-password"

    account = service.build_task_account_payload(first_shop_id)
    assert account.model_dump(mode="json") == {
        "shop_id": str(first_shop_id),
        "platform_code": "douyin",
        "login_identifier": "new-user",
        "secret": "updated-password",
        "preferred_verification_channel": "manual",
    }
    assert "updated-password" not in repr(account)

    service.bind(second_shop_id, credential.credential_id)
    assert len(bindings.list_by_credential(credential.credential_id)) == 2
