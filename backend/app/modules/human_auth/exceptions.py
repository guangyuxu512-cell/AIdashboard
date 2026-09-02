from app.core.exceptions import AppError


class HumanLoginFailedError(AppError):
    code = "HUMAN_LOGIN_FAILED"
    message = "登录账号或密码错误"
    status_code = 401


class HumanSessionInvalidError(AppError):
    code = "HUMAN_SESSION_INVALID"
    message = "登录会话已失效，请重新登录"
    status_code = 401


class HumanLoginNameConflictError(AppError):
    code = "HUMAN_LOGIN_NAME_CONFLICT"
    message = "登录账号已被使用"
    status_code = 409


class HumanBootstrapNotAllowedError(AppError):
    code = "HUMAN_BOOTSTRAP_NOT_ALLOWED"
    message = "系统已有人员账号，禁止执行首次初始化"
    status_code = 409


class DefaultTeamNotFoundError(AppError):
    code = "HUMAN_DEFAULT_TEAM_NOT_FOUND"
    message = "默认团队不存在或已停用，无法初始化首个人员账号"
    status_code = 500
