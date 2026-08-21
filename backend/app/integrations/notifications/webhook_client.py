from __future__ import annotations

from typing import Any

import httpx

from app.integrations.notifications.types import NotificationMessage
from app.modules.notifications.enums import NotificationChannelType


class NotificationDeliveryError(RuntimeError):
    pass


class WebhookNotificationAdapter:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self.client = client

    def send(
        self,
        channel_type: NotificationChannelType,
        webhook_url: str,
        message: NotificationMessage,
    ) -> None:
        try:
            payload = self._build_payload(channel_type, message)
            if self.client is None:
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(webhook_url, json=payload)
            else:
                response = self.client.post(webhook_url, json=payload)
            response.raise_for_status()
            self._validate_provider_response(channel_type, response)
        except (httpx.HTTPError, ValueError, NotificationDeliveryError):
            raise NotificationDeliveryError("Webhook delivery failed") from None

    @staticmethod
    def _build_payload(
        channel_type: NotificationChannelType,
        message: NotificationMessage,
    ) -> dict[str, Any]:
        content = message.render_text()
        if channel_type is NotificationChannelType.FEISHU_WEBHOOK:
            return {"msg_type": "text", "content": {"text": content}}
        return {"msgtype": "text", "text": {"content": content}}

    @staticmethod
    def _validate_provider_response(
        channel_type: NotificationChannelType,
        response: httpx.Response,
    ) -> None:
        data = response.json()
        if channel_type is NotificationChannelType.FEISHU_WEBHOOK:
            code = data.get("code", data.get("StatusCode", 0))
        else:
            code = data.get("errcode", 0)
        if code != 0:
            raise NotificationDeliveryError("Webhook provider rejected the message")
