"""Non-destructive real ShopSession -> Douyin identity verification.

Run explicitly from backend; this module is intentionally not pytest-collected.
"""

import argparse
import json

from sqlalchemy import select

from app.core.database import get_session_factory
from app.core.security import get_secret_cipher
from app.modules.sessions.auth_context import ShopSessionAccessor
from app.modules.shops.enums import ShopPlatform
from app.modules.shops.models import Shop
from app.modules.shops.platform_service import ShopPlatformService
from app.platforms.douyin import DouyinPlatformConnector


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shop-name", default="HuanYu")
    args = parser.parse_args()

    with get_session_factory()() as session:
        shop = session.scalar(select(Shop).where(Shop.display_name == args.shop_name))
        if shop is None:
            raise SystemExit("target shop not found")
        service = ShopPlatformService(
            session,
            ShopSessionAccessor(session, get_secret_cipher()),
            {ShopPlatform.DOUYIN: DouyinPlatformConnector()},
        )
        result = service.fetch_identity(shop.shop_id)
        print(
            json.dumps(
                {
                    "platform": result.platform.value,
                    "shop_display_name": result.shop_display_name,
                    "identity_matches": result.platform_shop_id == shop.platform_shop_id,
                    "session_status": result.session_status.value,
                    "management_profile_used": False,
                },
                ensure_ascii=False,
            ),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
