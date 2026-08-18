from enum import Enum


class ShopPlatform(str, Enum):
    DOUYIN = "douyin"
    PDD = "pdd"


class BindingRole(str, Enum):
    PRIMARY = "primary"
    BACKUP = "backup"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [str(member.value) for member in enum_class]
