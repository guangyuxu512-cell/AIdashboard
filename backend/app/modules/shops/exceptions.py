from app.core.exceptions import AppError


class ShopNotFoundError(AppError):
    code = "SHOP_NOT_FOUND"
    message = "店铺不存在"
    status_code = 404


class InvalidDeviceBindingError(AppError):
    code = "INVALID_DEVICE_BINDING"
    message = "设备绑定关系无效"
    status_code = 409


class ImmutableShopIdentityError(AppError):
    code = "IMMUTABLE_SHOP_IDENTITY"
    message = "平台识别店铺的名称与平台不可修改"
    status_code = 409
