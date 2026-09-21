from app.core.exceptions import AppError


class PlatformAuthenticationInvalidError(AppError):
    code = "AUTH_INVALID"
    message = "平台认证已失效，需要重新登录"
    status_code = 401


class PlatformRequestTimeoutError(AppError):
    code = "PLATFORM_TIMEOUT"
    message = "平台请求超时"
    status_code = 504


class PlatformRequestFailedError(AppError):
    code = "PLATFORM_REQUEST_FAILED"
    message = "平台请求失败"
    status_code = 502


class PlatformSignerFailedError(PlatformRequestFailedError):
    """The isolated platform signer failed before a platform request was sent."""

    code = "PLATFORM_SIGNER_FAILED"
    message = "平台签名服务失败"


class PlatformResponseInvalidError(AppError):
    code = "PLATFORM_RESPONSE_INVALID"
    message = "平台响应结构无效"
    status_code = 502


class PlatformIdentityMismatchError(AppError):
    code = "PLATFORM_IDENTITY_MISMATCH"
    message = "平台返回的店铺身份与当前店铺不一致"
    status_code = 409


class PlatformNotSupportedError(AppError):
    code = "PLATFORM_NOT_SUPPORTED"
    message = "当前平台尚未接入服务器请求"
    status_code = 422
