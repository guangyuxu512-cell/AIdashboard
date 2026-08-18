from app.core.exceptions import AppError


class UserNotFoundError(AppError):
    code = "USER_NOT_FOUND"
    message = "用户不存在"
    status_code = 404
