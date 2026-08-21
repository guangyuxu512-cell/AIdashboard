from app.core.exceptions import AppError


class ShopOnboardingConflictError(AppError):
    code = "SHOP_ONBOARDING_CONFLICT"
    message = "该平台店铺已经接入"
    status_code = 409


class InvalidSessionPayloadError(AppError):
    code = "INVALID_SESSION_PAYLOAD"
    message = "登录会话载荷无效"
    status_code = 422
