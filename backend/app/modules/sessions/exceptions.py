from app.core.exceptions import AppError


class SessionVersionConflictError(AppError):
    code = "SESSION_VERSION_CONFLICT"
    message = "Session 已被更新，请使用最新版本重试"
    status_code = 409


class SessionEncryptionUnavailableError(AppError):
    code = "SESSION_ENCRYPTION_UNAVAILABLE"
    message = "Session 加密服务不可用"
    status_code = 500
