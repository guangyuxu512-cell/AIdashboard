from app.core.exceptions import AppError


class HumanAuthenticationRequiredError(AppError):
    code = "HUMAN_AUTHENTICATION_REQUIRED"
    message = "需要有效的管理端用户身份"
    status_code = 401


class HumanUserDisabledError(AppError):
    code = "HUMAN_USER_DISABLED"
    message = "当前用户已停用"
    status_code = 403


class TeamNotFoundError(AppError):
    code = "TEAM_NOT_FOUND"
    message = "团队不存在"
    status_code = 404


class TeamDisabledError(AppError):
    code = "TEAM_DISABLED"
    message = "团队已停用"
    status_code = 409


class TeamMembershipNotFoundError(AppError):
    code = "TEAM_MEMBERSHIP_NOT_FOUND"
    message = "团队成员关系不存在"
    status_code = 404


class TeamMembershipConflictError(AppError):
    code = "TEAM_MEMBERSHIP_CONFLICT"
    message = "用户已加入该团队"
    status_code = 409


class TeamMembershipRequiredError(AppError):
    code = "TEAM_MEMBERSHIP_REQUIRED"
    message = "当前用户没有可用的团队成员关系"
    status_code = 403


class TeamContextRequiredError(AppError):
    code = "TEAM_CONTEXT_REQUIRED"
    message = "请先选择目标团队"
    status_code = 409


class TeamAccessDeniedError(AppError):
    code = "TEAM_ACCESS_DENIED"
    message = "当前用户无权使用指定团队"
    status_code = 403


class InvalidDataScopeError(AppError):
    code = "INVALID_DATA_SCOPE"
    message = "数据范围配置无效"
    status_code = 500


class AccessAdministrationForbiddenError(AppError):
    code = "ACCESS_ADMINISTRATION_FORBIDDEN"
    message = "当前用户无权管理用户与权限"
    status_code = 403


class SuperAccountRequiredError(AppError):
    code = "SUPER_ACCOUNT_REQUIRED"
    message = "仅超级账号可以维护公司公共资源"
    status_code = 403


class SuperAccountConflictError(AppError):
    code = "SUPER_ACCOUNT_CONFLICT"
    message = "系统已有其他超级账号；请先显式完成交接"
    status_code = 409


class ModuleAccessDeniedError(AppError):
    code = "MODULE_ACCESS_DENIED"
    message = "当前用户无权使用此功能模块"
    status_code = 403


class TeamResourceAccessDeniedError(AppError):
    code = "TEAM_RESOURCE_ACCESS_DENIED"
    message = "当前团队无权使用该资源"
    status_code = 403


class TeamResourceInvalidError(AppError):
    code = "TEAM_RESOURCE_INVALID"
    message = "团队授权包含不存在或已移除的资源"
    status_code = 422


class TeamInUseError(AppError):
    code = "TEAM_IN_USE"
    message = "团队仍有关联成员、资源授权或业务数据，只能归档"
    status_code = 409


class InvalidModuleAccessError(AppError):
    code = "INVALID_MODULE_ACCESS"
    message = "功能模块权限配置无效"
    status_code = 422


class LastAccessAdministratorRequiredError(AppError):
    code = "LAST_ACCESS_ADMINISTRATOR_REQUIRED"
    message = "系统至少需要保留一名可管理用户与权限的管理员"
    status_code = 409


class LastSuperAccountRequiredError(AppError):
    code = "LAST_SUPER_ACCOUNT_REQUIRED"
    message = "系统至少需要保留一个启用的超级账号"
    status_code = 409


class AccessAdministratorMembershipUnavailableError(AppError):
    code = "ACCESS_ADMINISTRATOR_MEMBERSHIP_UNAVAILABLE"
    message = "只能为启用用户、启用团队中的启用成员关系授予权限管理员"
    status_code = 409


class AccessMemberCredentialNotConfiguredError(AppError):
    code = "ACCESS_MEMBER_CREDENTIAL_NOT_CONFIGURED"
    message = "该员工尚未配置登录账号，无法重置密码"
    status_code = 409
