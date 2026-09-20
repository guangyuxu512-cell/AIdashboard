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


class AutomationParameterPresetInUseError(AppError):
    code = "AUTOMATION_PARAMETER_PRESET_IN_USE"
    message = "该配置已被历史任务或定时计划引用，无法删除"
    status_code = 409

    def __init__(self, reference_types: tuple[str, ...] = ()) -> None:
        super().__init__(details={"reference_types": list(reference_types)})


class AutomationParameterPresetInvalidError(AppError):
    code = "AUTOMATION_PARAMETER_PRESET_INVALID"
    message = "参数预设不符合当前应用参数契约"
    status_code = 422
