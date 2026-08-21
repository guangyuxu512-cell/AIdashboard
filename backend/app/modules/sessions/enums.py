from enum import Enum


class ShopSessionStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CAPTURED = "captured"
    VALID = "valid"
    INVALID = "invalid"
    REFRESH_REQUIRED = "refresh_required"
