from enum import StrEnum


class NotificationChannelType(StrEnum):
    FEISHU_WEBHOOK = "feishu_webhook"
    WECOM_WEBHOOK = "wecom_webhook"
