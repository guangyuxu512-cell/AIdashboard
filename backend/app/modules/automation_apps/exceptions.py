from app.core.exceptions import AppError


class AutomationParameterPresetNotFoundError(AppError):
    code = "AUTOMATION_PARAMETER_PRESET_NOT_FOUND"
    message = "参数预设不存在"
    status_code = 404


class AutomationParameterPresetConflictError(AppError):
    code = "AUTOMATION_PARAMETER_PRESET_CONFLICT"
    message = "当前团队中该应用的预设名称已存在"
    status_code = 409


class AutomationParameterPresetVersionConflictError(AppError):
    code = "AUTOMATION_PARAMETER_PRESET_VERSION_CONFLICT"
    message = "参数预设已被其他成员更新，请刷新后重新编辑"
    status_code = 409


class AutomationParameterPresetInvalidError(AppError):
    code = "AUTOMATION_PARAMETER_PRESET_INVALID"
    message = "参数预设不符合当前应用参数契约"
    status_code = 422
