from app.core.exceptions import AppError


class NotificationChannelNotFoundError(AppError):
    code = "NOTIFICATION_CHANNEL_NOT_FOUND"
    message = "通知通道不存在"
    status_code = 404


class NotificationDeliveryFailedError(AppError):
    code = "NOTIFICATION_DELIVERY_FAILED"
    message = "通知发送失败，请检查通道配置"
    status_code = 502
