"""Resolve task shop references from the target Worker's reported inventory."""
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.tasks.exceptions import TaskInputInvalidError
from app.modules.workers.precheck_models import WorkerRpaShopInventory


LOCAL_SHOPS_KEY = "_worker_local_shops"


def resolve_worker_shops(
    session: Session, device_id: UUID, local_shop_ids: list[str], *, require_available: bool = True,
) -> list[dict[str, Any]]:
    if not local_shop_ids:
        return []
    inventory = session.get(WorkerRpaShopInventory, device_id)
    if inventory is None or (require_available and not inventory.available):
        raise TaskInputInvalidError("设备当前无法读取本机店铺清单")
    shops = {item.get("localShopId"): item for item in inventory.shops if isinstance(item, dict)}
    result = []
    for local_id in local_shop_ids:
        item = shops.get(local_id)
        if item is None or not isinstance(item.get("platform"), str):
            raise TaskInputInvalidError("所选店铺不在该设备的本机店铺清单中")
        result.append({"local_shop_id": local_id, "platform": item["platform"],
                       "platform_shop_id": item.get("platformShopId")})
    return result


def worker_shop_snapshot_matches(
    session: Session, device_id: UUID, shops: list[dict[str, Any]], *, require_available: bool = True,
) -> bool:
    if not shops:
        return True
    try:
        current = resolve_worker_shops(session, device_id, [item["local_shop_id"] for item in shops],
                                       require_available=require_available)
    except (TaskInputInvalidError, KeyError, TypeError):
        return False
    return current == shops
