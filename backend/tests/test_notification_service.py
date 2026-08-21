from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr

from app.core.security import SecretCipher
from app.integrations.notifications import (
    NotificationDeliveryError,
    NotificationMessage,
    WebhookNotificationAdapter,
)
from app.modules.notifications.enums import NotificationChannelType
from app.modules.notifications.models import NotificationChannel
from app.modules.notifications.schemas import (
    NotificationChannelCreate,
    NotificationChannelUpdate,
)
from app.modules.notifications.service import NotificationService
from tests.support import FakeSession


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.channels: list[NotificationChannel] = []

    def list(self) -> list[NotificationChannel]:
        return self.channels

    def list_enabled(self) -> list[NotificationChannel]:
        return [channel for channel in self.channels if channel.enabled]

    def get(self, channel_id: object) -> NotificationChannel | None:
        return next(
            (channel for channel in self.channels if channel.channel_id == channel_id),
            None,
        )

    def add(self, channel: NotificationChannel) -> None:
        now = datetime.now(UTC)
        channel.channel_id = uuid4()
        channel.created_at = now
        channel.updated_at = now
        self.channels.append(channel)


class CaptureAdapter:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[tuple[NotificationChannelType, str, str]] = []

    def send(
        self,
        channel_type: NotificationChannelType,
        webhook_url: str,
        message: NotificationMessage,
    ) -> None:
        self.sent.append((channel_type, webhook_url, message.render_text()))
        if self.fail:
            raise NotificationDeliveryError("failed")


def build_service(
    *,
    adapter: CaptureAdapter | None = None,
) -> tuple[NotificationService, FakeNotificationRepository, CaptureAdapter]:
    repository = FakeNotificationRepository()
    capture = adapter or CaptureAdapter()
    service = NotificationService(  # type: ignore[arg-type]
        FakeSession(),
        SecretCipher(Fernet.generate_key().decode("ascii")),
        repository,
        capture,
    )
    return service, repository, capture


def test_channel_encrypts_webhook_and_blank_update_preserves_secret() -> None:
    service, repository, adapter = build_service()
    read = service.create_channel(
        NotificationChannelCreate(
            channel_type=NotificationChannelType.FEISHU_WEBHOOK,
            name="运营通知",
            webhook_url=SecretStr("https://example.invalid/secret-hook"),
        ),
    )
    channel = repository.channels[0]

    assert read.webhook_configured is True
    assert b"secret-hook" not in channel.webhook_url_encrypted
    encrypted_before = channel.webhook_url_encrypted
    service.update_channel(
        read.channel_id,
        NotificationChannelUpdate(webhook_url="", enabled=False),
    )
    assert channel.webhook_url_encrypted == encrypted_before

    service.send_test(read.channel_id, now=datetime.now(UTC))
    assert adapter.sent[0][1] == "https://example.invalid/secret-hook"
    assert "中控台通知测试" in adapter.sent[0][2]


def test_event_switches_and_delivery_failure_do_not_escape(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter = CaptureAdapter(fail=True)
    service, repository, _ = build_service(adapter=adapter)
    read = service.create_channel(
        NotificationChannelCreate(
            channel_type=NotificationChannelType.WECOM_WEBHOOK,
            name="设备通知",
            webhook_url=SecretStr("https://example.invalid/private-webhook"),
            device_offline_enabled=True,
            device_recovered_enabled=False,
        ),
    )

    service.notify_device_offline(
        device_name="PC-A",
        last_heartbeat=datetime.now(UTC),
    )
    service.notify_device_recovered(device_name="PC-A", offline_duration=None)
    assert len(adapter.sent) == 1

    repository.channels[0].enabled = False
    service.notify_device_offline(
        device_name="PC-A",
        last_heartbeat=datetime.now(UTC),
    )
    assert len(adapter.sent) == 1
    assert "private-webhook" not in caplog.text
    assert read.webhook_configured is True


def test_webhook_adapter_formats_feishu_and_wecom_payloads() -> None:
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"code": 0, "errcode": 0})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = WebhookNotificationAdapter(client)
    message = NotificationMessage(title="标题", lines=("正文",))
    adapter.send(
        NotificationChannelType.FEISHU_WEBHOOK,
        "https://example.invalid/feishu",
        message,
    )
    adapter.send(
        NotificationChannelType.WECOM_WEBHOOK,
        "https://example.invalid/wecom",
        message,
    )

    assert payloads[0] == {
        "msg_type": "text",
        "content": {"text": "标题\n\n正文"},
    }
    assert payloads[1] == {
        "msgtype": "text",
        "text": {"content": "标题\n\n正文"},
    }
    client.close()
