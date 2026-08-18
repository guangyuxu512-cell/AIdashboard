from app.core.exceptions import AppError


class CredentialNotFoundError(AppError):
    code = "CREDENTIAL_NOT_FOUND"
    message = "账号凭证不存在"
    status_code = 404


class CredentialAlreadyConfiguredError(AppError):
    code = "CREDENTIAL_ALREADY_CONFIGURED"
    message = "店铺已经配置启用的账号凭证"
    status_code = 409


class InvalidCredentialBindingError(AppError):
    code = "INVALID_CREDENTIAL_BINDING"
    message = "账号凭证与店铺关系无效"
    status_code = 409
