from app.core.exceptions import AppError


class TaskNotFoundError(AppError):
    code = "TASK_NOT_FOUND"
    message = "任务不存在"
    status_code = 404


class TaskStateConflictError(AppError):
    code = "TASK_STATE_CONFLICT"
    message = "任务状态已变更，无法完成当前操作"
    status_code = 409


class TaskTargetDeviceInvalidError(AppError):
    code = "TASK_TARGET_DEVICE_INVALID"
    message = "目标设备不存在或已停用"
    status_code = 422


class TaskInputInvalidError(AppError):
    code = "TASK_INPUT_INVALID"
    message = "Skill 输入不符合契约"
    status_code = 422


class TaskProviderUnavailableError(AppError):
    code = "TASK_PROVIDER_UNAVAILABLE"
    message = "目标设备的执行能力当前不可用"
    status_code = 422


class TaskEventForbiddenError(AppError):
    code = "TASK_EVENT_FORBIDDEN"
    message = "当前 Worker 无权为该任务写入运行事件"
    status_code = 403
