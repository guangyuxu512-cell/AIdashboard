from app.core.exceptions import AppError


class DeviceNotFoundError(AppError):
    code = "DEVICE_NOT_FOUND"
    message = "设备不存在"
    status_code = 404
