from app.core.exceptions import AppError


class ShopNotFoundError(AppError):
    code = "SHOP_NOT_FOUND"
    message = "店铺不存在"
    status_code = 404


class InvalidDeviceBindingError(AppError):
    code = "INVALID_DEVICE_BINDING"
    message = "设备绑定关系无效"
    status_code = 409
