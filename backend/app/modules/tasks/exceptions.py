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


class TaskDeviceDisabledError(AppError):
    code = "TASK_DEVICE_DISABLED"
    message = "目标设备已停用"
    status_code = 422


class TaskWorkerOfflineError(AppError):
    code = "TASK_WORKER_OFFLINE"
    message = "目标设备 Worker 当前离线"
    status_code = 422


class TaskShopInvalidError(AppError):
    code = "TASK_SHOP_INVALID"
    message = "任务包含不存在、已停用或已删除的店铺"
    status_code = 422


class TaskShopDeviceBindingInvalidError(AppError):
    code = "TASK_SHOP_DEVICE_BINDING_INVALID"
    message = "任务包含未授权给目标设备的店铺"
    status_code = 422


class TaskAssetInvalidError(AppError):
    code = "TASK_ASSET_INVALID"
    message = "任务包含不存在或不支持传输的图片资产"
    status_code = 422


class TaskInputInvalidError(AppError):
    code = "TASK_INPUT_INVALID"
    message = "Skill 输入不符合契约"
    status_code = 422


class TaskSkillNotAvailableError(AppError):
    code = "TASK_SKILL_NOT_AVAILABLE"
    message = "目标设备未声明所需 Skill"
    status_code = 422


class TaskSkillSchemaUnavailableError(AppError):
    code = "TASK_SKILL_SCHEMA_UNAVAILABLE"
    message = "目标设备未提供可用的业务 Skill 输入契约"
    status_code = 422


class TaskProviderNotReadyError(AppError):
    code = "TASK_PROVIDER_NOT_READY"
    message = "目标设备的 Provider 尚未就绪"
    status_code = 422


class TaskProviderLoginRequiredError(AppError):
    code = "TASK_PROVIDER_LOGIN_REQUIRED"
    message = "目标设备的影刀需要登录"
    status_code = 422


class TaskProviderVersionUnsupportedError(AppError):
    code = "TASK_PROVIDER_VERSION_UNSUPPORTED"
    message = "目标设备的影刀版本不受支持"
    status_code = 422


class TaskApplicationNotAvailableError(AppError):
    code = "TASK_APPLICATION_NOT_AVAILABLE"
    message = "当前影刀账号无法访问该应用"
    status_code = 422


class TaskEventForbiddenError(AppError):
    code = "TASK_EVENT_FORBIDDEN"
    message = "当前 Worker 无权为该任务写入运行事件"
    status_code = 403
