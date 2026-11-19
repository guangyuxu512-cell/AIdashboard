from app.core.exceptions import AppError


class ApiTokenInvalidError(AppError):
    code = "API_TOKEN_INVALID"
    message = "Token 无效、已过期或已撤销"
    status_code = 401


class ApiTokenPermissionDeniedError(AppError):
    code = "API_TOKEN_PERMISSION_DENIED"
    message = "Token 没有此操作的权限"
    status_code = 403


class ApiTokenInputError(AppError):
    code = "API_TOKEN_INPUT_INVALID"
    message = "Token 权限或有效期无效"
    status_code = 422


class ApiTokenNotFoundError(AppError):
    code = "API_TOKEN_NOT_FOUND"
    message = "Token 不存在"
    status_code = 404


class ApiTokenRecoveryUnavailableError(AppError):
    code = "API_TOKEN_RECOVERY_UNAVAILABLE"
    message = "Token 查看密钥尚未配置"
    status_code = 503


class ApiTokenNotRecoverableError(AppError):
    code = "API_TOKEN_NOT_RECOVERABLE"
    message = "该 Token 无法从当前服务恢复，请使用原有保存位置"
    status_code = 409
