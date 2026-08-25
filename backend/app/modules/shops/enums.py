from enum import Enum


class ShopPlatform(str, Enum):
    DOUYIN = "douyin"
    PDD = "pdd"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [str(member.value) for member in enum_class]
