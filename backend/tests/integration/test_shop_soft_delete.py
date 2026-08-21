from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import Engine, delete
from sqlalchemy.orm import Session

from app.modules.credentials.enums import VerificationChannel
from app.modules.credentials.models import PlatformCredential, ShopCredentialBinding
from app.modules.devices.models import Device
from app.modules.sessions.enums import ShopSessionStatus
from app.modules.sessions.models import ShopSession
from app.modules.shops.enums import BindingRole, ShopPlatform
from app.modules.shops.models import Shop, ShopDeviceBinding
from app.modules.shops.repository import ShopRepository
from app.modules.shops.service import ShopService


pytestmark = pytest.mark.integration


def test_soft_remove_preserves_auth_facts_and_disables_bindings(
    postgresql_engine: Engine,
) -> None:
    shop_id = uuid4()
    device_id = uuid4()
    credential_id = uuid4()
    session_id = uuid4()
    now = datetime.now(UTC)

    try:
        with Session(postgresql_engine) as session:
            session.add_all(
                [
                    Shop(
                        shop_id=shop_id,
                        display_name="stage-shop-soft-delete",
                        platform=ShopPlatform.DOUYIN,
                        platform_shop_id=f"stage-shop-{shop_id}",
                        enabled=True,
                    ),
                    Device(
                        device_id=device_id,
                        display_name="stage-shop-soft-delete-device",
                    ),
                    PlatformCredential(
                        credential_id=credential_id,
                        platform_code=ShopPlatform.DOUYIN,
                        login_identifier="stage-shop-soft-delete-account",
                        secret_encrypted=b"encrypted-test-secret",
                        preferred_verification_channel=VerificationChannel.MANUAL,
                    ),
                ],
            )
            session.flush()
            session.add_all(
                [
                    ShopDeviceBinding(
                        shop_id=shop_id,
                        device_id=device_id,
                        binding_role=BindingRole.PRIMARY,
                        enabled=True,
                    ),
                    ShopCredentialBinding(
                        shop_id=shop_id,
                        credential_id=credential_id,
                        enabled=True,
                    ),
                    ShopSession(
                        session_id=session_id,
                        shop_id=shop_id,
                        version=1,
                        status=ShopSessionStatus.VALID,
                        captured_at=now,
                        validated_at=now,
                        payload_encrypted=b"encrypted-test-session",
                    ),
                ],
            )
            session.commit()

        with Session(postgresql_engine) as session:
            service = ShopService(session)
            service.remove(shop_id)

            assert ShopRepository(session).get(shop_id) is None
            stored_shop = ShopRepository(session).get_including_deleted(shop_id)
            assert stored_shop is not None
            assert stored_shop.enabled is False
            assert stored_shop.deleted_at is not None
            binding = session.get(ShopDeviceBinding, (shop_id, device_id))
            assert binding is not None
            assert binding.enabled is False
            assert session.get(PlatformCredential, credential_id) is not None
            assert session.get(ShopCredentialBinding, (shop_id, credential_id)) is not None
            assert session.get(ShopSession, session_id) is not None
            shops, _, statuses = service.list(offset=0, limit=100)
            assert shop_id not in {shop.shop_id for shop in shops}
            assert shop_id not in statuses
    finally:
        with Session(postgresql_engine) as session:
            session.execute(delete(ShopSession).where(ShopSession.shop_id == shop_id))
            session.execute(
                delete(ShopCredentialBinding).where(
                    ShopCredentialBinding.shop_id == shop_id,
                ),
            )
            session.execute(
                delete(ShopDeviceBinding).where(ShopDeviceBinding.shop_id == shop_id),
            )
            session.execute(delete(Shop).where(Shop.shop_id == shop_id))
            session.execute(
                delete(PlatformCredential).where(
                    PlatformCredential.credential_id == credential_id,
                ),
            )
            session.execute(delete(Device).where(Device.device_id == device_id))
            session.commit()
