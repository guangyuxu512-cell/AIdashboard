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
