from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.security import SecretCipher
from app.integrations.notifications import (
    NotificationDeliveryError,
    NotificationMessage,
    WebhookNotificationAdapter,
)
from app.modules.notifications.enums import NotificationChannelType
from app.modules.notifications.exceptions import (
    NotificationChannelNotFoundError,
    NotificationDeliveryFailedError,
)
from app.modules.notifications.models import NotificationChannel
from app.modules.notifications.repository import NotificationChannelRepository
from app.modules.notifications.schemas import (
    NotificationChannelCreate,
    NotificationChannelRead,
    NotificationChannelUpdate,
)


logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        session: Session,
        cipher: SecretCipher,
        repository: NotificationChannelRepository | None = None,
        adapter: WebhookNotificationAdapter | None = None,
    ) -> None:
        self.session = session
        self.cipher = cipher
        self.repository = repository or NotificationChannelRepository(session)
        self.adapter = adapter or WebhookNotificationAdapter()

    def list_channels(self) -> list[NotificationChannelRead]:
        return [self._to_read(channel) for channel in self.repository.list()]

    def create_channel(
        self,
        data: NotificationChannelCreate,
    ) -> NotificationChannelRead:
        channel = NotificationChannel(
            channel_type=data.channel_type.value,
            name=data.name,
            enabled=data.enabled,
            webhook_url_encrypted=self.cipher.encrypt_text(
                data.webhook_url.get_secret_value(),
            ),
            device_offline_enabled=data.device_offline_enabled,
            device_recovered_enabled=data.device_recovered_enabled,
        )
        self.repository.add(channel)
        self.session.commit()
        self.session.refresh(channel)
        return self._to_read(channel)

    def update_channel(
        self,
        channel_id: UUID,
        data: NotificationChannelUpdate,
    ) -> NotificationChannelRead:
        channel = self._get(channel_id)
        changes = data.model_dump(exclude_unset=True)
        webhook_url = changes.pop("webhook_url", None)
        if webhook_url is not None:
            channel.webhook_url_encrypted = self.cipher.encrypt_text(
                webhook_url.get_secret_value(),
            )
        channel_type = changes.pop("channel_type", None)
        if channel_type is not None:
            channel.channel_type = channel_type.value
        for field, value in changes.items():
            if value is not None:
                setattr(channel, field, value)
        self.session.commit()
        self.session.refresh(channel)
        return self._to_read(channel)

    def send_test(self, channel_id: UUID, *, now: datetime) -> None:
        channel = self._get(channel_id)
        message = NotificationMessage(
            title="中控台通知测试",
            lines=("通知通道配置成功。", f"时间：{now.isoformat()}"),
        )
        try:
            self._send(channel, message)
        except NotificationDeliveryError as error:
            logger.warning(
                "Notification test failed channel_id=%s channel_type=%s",
                channel.channel_id,
                channel.channel_type,
            )
            raise NotificationDeliveryFailedError() from error

    def notify_device_offline(
        self,
        *,
        device_name: str,
        last_heartbeat: datetime,
    ) -> None:
        message = NotificationMessage(
            title="【设备离线】",
            lines=(
                f"设备：{device_name}",
                "状态：离线",
                f"最后心跳：{last_heartbeat.isoformat()}",
            ),
        )
        self._dispatch_event(message, event="device_offline")

    def notify_device_recovered(
        self,
        *,
        device_name: str,
        offline_duration: timedelta | None,
    ) -> None:
        lines = [f"设备：{device_name}", "状态：已恢复在线"]
        if offline_duration is not None:
            seconds = max(0, int(offline_duration.total_seconds()))
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            duration_parts = []
            if hours:
                duration_parts.append(f"{hours}小时")
            if minutes:
                duration_parts.append(f"{minutes}分")
            duration_parts.append(f"{seconds}秒")
            lines.append(f"离线时长：{''.join(duration_parts)}")
        self._dispatch_event(
            NotificationMessage(title="【设备恢复】", lines=tuple(lines)),
            event="device_recovered",
        )

    def _dispatch_event(
        self,
        message: NotificationMessage,
        *,
        event: str,
    ) -> None:
        for channel in self.repository.list_enabled():
            if event == "device_offline" and not channel.device_offline_enabled:
                continue
            if event == "device_recovered" and not channel.device_recovered_enabled:
                continue
            try:
                self._send(channel, message)
            except NotificationDeliveryError:
                logger.warning(
                    "Notification delivery failed channel_id=%s channel_type=%s event=%s",
                    channel.channel_id,
                    channel.channel_type,
                    event,
                )

    def _send(
        self,
        channel: NotificationChannel,
        message: NotificationMessage,
    ) -> None:
        self.adapter.send(
            NotificationChannelType(channel.channel_type),
            self.cipher.decrypt_text(channel.webhook_url_encrypted),
            message,
        )

    def _get(self, channel_id: UUID) -> NotificationChannel:
        channel = self.repository.get(channel_id)
        if channel is None:
            raise NotificationChannelNotFoundError()
        return channel

    @staticmethod
    def _to_read(channel: NotificationChannel) -> NotificationChannelRead:
        return NotificationChannelRead(
            channel_id=channel.channel_id,
            channel_type=channel.channel_type,
            name=channel.name,
            enabled=channel.enabled,
            webhook_configured=bool(channel.webhook_url_encrypted),
            device_offline_enabled=channel.device_offline_enabled,
            device_recovered_enabled=channel.device_recovered_enabled,
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )
