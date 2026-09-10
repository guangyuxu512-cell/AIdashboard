from app.core.exceptions import AppError


class ScheduleNotFoundError(AppError):
    code = "SCHEDULE_NOT_FOUND"
    message = "定时计划不存在"
    status_code = 404


class ScheduleRuleInvalidError(AppError):
    code = "SCHEDULE_RULE_INVALID"
    message = "定时计划重复规则无效"
    status_code = 422
