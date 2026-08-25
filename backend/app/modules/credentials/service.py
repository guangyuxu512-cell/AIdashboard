from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import SecretCipher, mask_login_identifier
from app.modules.credentials.exceptions import (
    CredentialAlreadyConfiguredError,
    CredentialNotFoundError,
    InvalidCredentialBindingError,
)
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.credentials.repository import (
    CredentialRepository,
    ShopCredentialBindingRepository,
)
from app.modules.credentials.schemas import (
    CredentialCreate,
    CredentialStatusRead,
    CredentialUpdate,
    TaskAccountPayload,
)
from app.modules.shops.exceptions import ShopNotFoundError
from app.modules.shops.models import Shop
from app.modules.shops.repository import ShopRepository


class CredentialService:
    def __init__(
        self,
        session: Session,
        cipher: SecretCipher,
        credential_repository: CredentialRepository | None = None,
        binding_repository: ShopCredentialBindingRepository | None = None,
        shop_repository: ShopRepository | None = None,
    ) -> None:
        self.session = session
        self.cipher = cipher
        self.credential_repository = credential_repository or CredentialRepository(
            session,
        )
        self.binding_repository = binding_repository or ShopCredentialBindingRepository(
            session,
        )
        self.shop_repository = shop_repository or ShopRepository(session)

    def _get_shop(self, shop_id: UUID) -> Shop:
        shop = self.shop_repository.get(shop_id)
        if shop is None:
            raise ShopNotFoundError()
        return shop

    def get(self, credential_id: UUID) -> PlatformCredential:
        credential = self.credential_repository.get(credential_id)
        if credential is None:
            raise CredentialNotFoundError()
        return credential

    def get_status_for_shop(self, shop_id: UUID) -> CredentialStatusRead:
        shop = self._get_shop(shop_id)
        result = self.binding_repository.get_latest_by_shop(shop_id)
        if result is None:
            return CredentialStatusRead(
                credential_id=None,
                platform=shop.platform,
                masked_identifier=None,
                configured=False,
                enabled=False,
                preferred_verification_channel=None,
                updated_at=None,
            )

        binding, credential = result
        return self._to_status(
            credential,
            enabled=binding.enabled and credential.enabled,
        )

    def ensure_task_account_available(self, shop_id: UUID) -> None:
        self._get_active_task_credential(shop_id)

    def ensure_task_accounts_available(self, shop_ids: list[UUID]) -> None:
        self._get_active_task_credentials(shop_ids)

    def build_task_account_payload(self, shop_id: UUID) -> TaskAccountPayload:
        credential = self._get_active_task_credential(shop_id)
        return TaskAccountPayload(
            shop_id=shop_id,
            platform_code=credential.platform_code,
            login_identifier=credential.login_identifier,
            secret=self.cipher.decrypt_text(credential.secret_encrypted),
            preferred_verification_channel=(
                credential.preferred_verification_channel
            ),
        )

    def build_task_account_payloads(
        self,
        shop_ids: list[UUID],
    ) -> list[TaskAccountPayload]:
        credentials = self._get_active_task_credentials(shop_ids)
        return [
            TaskAccountPayload(
                shop_id=shop_id,
                platform_code=credential.platform_code,
                login_identifier=credential.login_identifier,
                secret=self.cipher.decrypt_text(credential.secret_encrypted),
                preferred_verification_channel=(
                    credential.preferred_verification_channel
                ),
            )
            for shop_id, credential in zip(shop_ids, credentials, strict=True)
        ]

    def _get_active_task_credentials(
        self,
        shop_ids: list[UUID],
    ) -> list[PlatformCredential]:
        if not shop_ids:
            return []
        shops = {shop.shop_id: shop for shop in self.shop_repository.list_by_ids(shop_ids)}
        active = self.binding_repository.list_active_by_shops(shop_ids)
        credentials: list[PlatformCredential] = []
        for shop_id in shop_ids:
            shop = shops.get(shop_id)
            if shop is None:
                raise ShopNotFoundError(details={"shop_id": str(shop_id)})
            result = active.get(shop_id)
            if result is None:
                raise CredentialNotFoundError(details={"shop_id": str(shop_id)})
            _, credential = result
            if credential.platform_code != shop.platform:
                raise InvalidCredentialBindingError(
                    details={"shop_id": str(shop_id)},
                )
            credentials.append(credential)
        return credentials

    def _get_active_task_credential(self, shop_id: UUID) -> PlatformCredential:
        shop = self._get_shop(shop_id)
        result = self.binding_repository.get_active_by_shop(shop_id)
        if result is None:
            raise CredentialNotFoundError()
        _, credential = result
        if credential.platform_code != shop.platform:
            raise InvalidCredentialBindingError()
        return credential

    def create(self, data: CredentialCreate) -> CredentialStatusRead:
        shop = self._get_shop(data.shop_id)
        if self.binding_repository.get_active_by_shop(data.shop_id) is not None:
            raise CredentialAlreadyConfiguredError()

        credential = PlatformCredential(
            platform_code=shop.platform,
            login_identifier=data.login_identifier,
            secret_encrypted=self.cipher.encrypt_text(data.secret.get_secret_value()),
            preferred_verification_channel=data.preferred_verification_channel,
            enabled=True,
        )
        self.credential_repository.add(credential)
        self.session.flush()
        binding = ShopCredentialBinding(
            shop_id=shop.shop_id,
            credential_id=credential.credential_id,
            enabled=True,
        )
        self.binding_repository.add(binding)
        self._commit_or_conflict()
        self.session.refresh(credential)
        return self._to_status(credential, enabled=True)

    def bind(self, shop_id: UUID, credential_id: UUID) -> ShopCredentialBinding:
        shop = self._get_shop(shop_id)
        credential = self.get(credential_id)
        if credential.platform_code != shop.platform or not credential.enabled:
            raise InvalidCredentialBindingError()
        if self.binding_repository.get_active_by_shop(shop_id) is not None:
            raise CredentialAlreadyConfiguredError()

        binding = self.binding_repository.get(shop_id, credential_id)
        if binding is None:
            binding = ShopCredentialBinding(
                shop_id=shop_id,
                credential_id=credential_id,
                enabled=True,
            )
            self.binding_repository.add(binding)
        else:
            binding.enabled = True
        self._commit_or_conflict()
        self.session.refresh(binding)
        return binding

    def update(
        self,
        credential_id: UUID,
        data: CredentialUpdate,
    ) -> CredentialStatusRead:
        credential = self.get(credential_id)
        changes = data.model_dump(exclude_unset=True)
        login_identifier = changes.get("login_identifier")
        if login_identifier is not None:
            credential.login_identifier = login_identifier
        secret = changes.get("secret")
        if secret is not None:
            credential.secret_encrypted = self.cipher.encrypt_text(
                secret.get_secret_value(),
            )
        channel = changes.get("preferred_verification_channel")
        if channel is not None:
            credential.preferred_verification_channel = channel

        self.session.commit()
        self.session.refresh(credential)
        return self._to_status(credential, enabled=credential.enabled)

    def disable(self, credential_id: UUID) -> CredentialStatusRead:
        credential = self.get(credential_id)
        credential.enabled = False
        for binding in self.binding_repository.list_by_credential(credential_id):
            binding.enabled = False
        self.session.commit()
        self.session.refresh(credential)
        return self._to_status(credential, enabled=False)

    def _commit_or_conflict(self) -> None:
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise CredentialAlreadyConfiguredError() from error

    @staticmethod
    def _to_status(
        credential: PlatformCredential,
        *,
        enabled: bool,
    ) -> CredentialStatusRead:
        return CredentialStatusRead(
            credential_id=credential.credential_id,
            platform=credential.platform_code,
            masked_identifier=mask_login_identifier(credential.login_identifier),
            configured=True,
            enabled=enabled,
            preferred_verification_channel=credential.preferred_verification_channel,
            updated_at=credential.updated_at,
        )
