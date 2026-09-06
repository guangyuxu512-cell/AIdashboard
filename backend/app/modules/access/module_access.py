from collections.abc import Iterable
from enum import StrEnum


class ModuleCode(StrEnum):
    """Backend enforcement codes for modules registered by the PC Module Registry."""

    SHOP = "shop"
    ASSET = "asset"
    AI_WORKBENCH = "ai-workbench"
    DEVICE = "device"
    TASK = "task"
    SCHEDULE = "schedule"
    SETTINGS = "settings"


MODULE_ACCESS_CODES = frozenset(ModuleCode)


def module_codes_are_unique(codes: Iterable[ModuleCode]) -> bool:
    values = tuple(codes)
    return len(values) == len(set(values))
