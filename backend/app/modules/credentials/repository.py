from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding


class CredentialRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, credential_id: UUID) -> PlatformCredential | None:
        return self.session.get(PlatformCredential, credential_id)

    def add(self, credential: PlatformCredential) -> None:
        self.session.add(credential)


class ShopCredentialBindingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, shop_id: UUID, credential_id: UUID) -> ShopCredentialBinding | None:
        return self.session.get(ShopCredentialBinding, (shop_id, credential_id))

    def get_active_by_shop(
        self,
        shop_id: UUID,
    ) -> tuple[ShopCredentialBinding, PlatformCredential] | None:
        statement = (
            select(ShopCredentialBinding, PlatformCredential)
            .join(
                PlatformCredential,
                PlatformCredential.credential_id
                == ShopCredentialBinding.credential_id,
            )
            .where(
                ShopCredentialBinding.shop_id == shop_id,
                ShopCredentialBinding.enabled.is_(True),
                PlatformCredential.enabled.is_(True),
            )
        )
        return self.session.execute(statement).one_or_none()

    def get_latest_by_shop(
        self,
        shop_id: UUID,
    ) -> tuple[ShopCredentialBinding, PlatformCredential] | None:
        statement = (
            select(ShopCredentialBinding, PlatformCredential)
            .join(
                PlatformCredential,
                PlatformCredential.credential_id
                == ShopCredentialBinding.credential_id,
            )
            .where(ShopCredentialBinding.shop_id == shop_id)
            .order_by(
                ShopCredentialBinding.enabled.desc(),
                ShopCredentialBinding.updated_at.desc(),
            )
            .limit(1)
        )
        return self.session.execute(statement).one_or_none()

    def list_by_credential(self, credential_id: UUID) -> list[ShopCredentialBinding]:
        statement = select(ShopCredentialBinding).where(
            ShopCredentialBinding.credential_id == credential_id,
        )
        return list(self.session.scalars(statement))

    def add(self, binding: ShopCredentialBinding) -> None:
        self.session.add(binding)
