from app.core.exceptions import AppError


class DeviceNotFoundError(AppError):
    code = "DEVICE_NOT_FOUND"
    message = "设备不存在"
    status_code = 404


class DeviceHasActiveTasksError(AppError):
    code = "DEVICE_HAS_ACTIVE_TASKS"
    message = "设备存在待执行或执行中的任务，暂时无法移除"
    status_code = 409
