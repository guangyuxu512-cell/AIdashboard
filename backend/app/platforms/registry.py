from app.modules.shops.enums import ShopPlatform
from app.platforms.base import PlatformConnector
from app.platforms.douyin import DouyinPlatformConnector
from app.platforms.pdd import PddPlatformConnector


def create_platform_connectors() -> dict[ShopPlatform, PlatformConnector]:
    """Construct the currently supported server-side Session connectors."""

    return {
        ShopPlatform.DOUYIN: DouyinPlatformConnector(),
        ShopPlatform.PDD: PddPlatformConnector(),
    }
