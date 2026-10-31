from app.core.exceptions import AppError


class SessionVersionConflictError(AppError):
    code = "SESSION_VERSION_CONFLICT"
    message = "Session 已被更新，请使用最新版本重试"
    status_code = 409


class SessionEncryptionUnavailableError(AppError):
    code = "SESSION_ENCRYPTION_UNAVAILABLE"
    message = "Session 加密服务不可用"
    status_code = 500


class ShopSessionNotConfiguredError(AppError):
    code = "SHOP_SESSION_NOT_CONFIGURED"
    message = "店铺尚未配置可用 Session"
    status_code = 409


class ShopSessionPayloadInvalidError(AppError):
    code = "SHOP_SESSION_PAYLOAD_INVALID"
    message = "店铺 Session 无法安全读取"
    status_code = 500


class ShopSessionAuthenticationInvalidError(AppError):
    code = "AUTH_INVALID"
    message = "店铺 Session 已失效，需要重新登录"
    status_code = 401


class ShopSessionReadBusyError(AppError):
    code = "PRECHECK_SESSION_AUTHORIZATION_BUSY"
    message = "店铺授权正在变更，请稍后重试"
    status_code = 409


class SessionRefreshLeaseConflictError(AppError):
    code = "SESSION_REFRESH_IN_PROGRESS"
    message = "该店铺正在其他窗口恢复登录会话"
    status_code = 409


class SessionRefreshLeaseInvalidError(AppError):
    code = "SESSION_REFRESH_LEASE_INVALID"
    message = "Session 恢复租约不存在或已过期"
    status_code = 409
