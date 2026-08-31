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
    message = "当前用户属于多个团队，请指定团队上下文"
    status_code = 409


class TeamAccessDeniedError(AppError):
    code = "TEAM_ACCESS_DENIED"
    message = "当前用户无权使用指定团队"
    status_code = 403


class InvalidDataScopeError(AppError):
    code = "INVALID_DATA_SCOPE"
    message = "数据范围配置无效"
    status_code = 500
