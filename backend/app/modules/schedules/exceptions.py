from app.core.exceptions import AppError


class ScheduleNotFoundError(AppError):
    code = "SCHEDULE_NOT_FOUND"
    message = "定时计划不存在"
    status_code = 404
