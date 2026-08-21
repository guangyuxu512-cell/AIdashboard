from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread
from uuid import uuid4

from cryptography.fernet import Fernet

from app.core.config import Settings
from app.core.security import SecretCipher
from app.integrations.notifications import WebhookNotificationAdapter
from app.modules.devices.models import Device
from app.modules.notifications.enums import NotificationChannelType
from app.modules.notifications.models import NotificationChannel
from app.modules.notifications.service import NotificationService
from app.modules.workers.schemas import WorkerHeartbeat
from app.modules.workers.service import WorkerPrincipal, WorkerService
from tests.support import FakeSession
from tests.test_notification_service import FakeNotificationRepository
from tests.test_worker_core import FakeWorkerRepository


class RecordingWebhookHandler(BaseHTTPRequestHandler):
    payloads: list[dict[str, object]] = []

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler contract
        size = int(self.headers.get("Content-Length", "0"))
        self.payloads.append(json.loads(self.rfile.read(size)))
        body = b'{"code":0}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        del format, args


def test_runtime_transitions_send_once_through_fake_webhook_server() -> None:
    RecordingWebhookHandler.payloads = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), RecordingWebhookHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cipher = SecretCipher(Fernet.generate_key().decode("ascii"))
        notification_repository = FakeNotificationRepository()
        channel = NotificationChannel(
            channel_id=uuid4(),
            channel_type=NotificationChannelType.FEISHU_WEBHOOK.value,
            name="fake webhook",
            enabled=True,
            webhook_url_encrypted=cipher.encrypt_text(
                f"http://127.0.0.1:{server.server_port}/hook",
            ),
            device_offline_enabled=True,
            device_recovered_enabled=True,
        )
        notification_repository.channels.append(channel)
        notification_service = NotificationService(  # type: ignore[arg-type]
            FakeSession(),
            cipher,
            notification_repository,
            WebhookNotificationAdapter(),
        )

        device = Device(device_id=uuid4(), display_name="Fake Webhook PC", enabled=True)
        worker_repository = FakeWorkerRepository(device)
        worker_service = WorkerService(  # type: ignore[arg-type]
            FakeSession(),
            worker_repository,
            Settings(worker_online_timeout_seconds=45),
            notification_service,
        )
        principal = WorkerPrincipal(device_id=device.device_id)
        now = datetime.now(UTC)
        heartbeat = WorkerHeartbeat(worker_version="0.1.0", started_at=now)
        worker_service.heartbeat(principal, heartbeat, now=now)

        assert worker_service.reconcile_offline_devices(
            now=now + timedelta(seconds=46),
        ) == 1
        assert worker_service.reconcile_offline_devices(
            now=now + timedelta(seconds=60),
        ) == 0
        assert len(RecordingWebhookHandler.payloads) == 1
        assert "【设备离线】" in json.dumps(
            RecordingWebhookHandler.payloads[0],
            ensure_ascii=False,
        )

        worker_service.heartbeat(
            principal,
            heartbeat,
            now=now + timedelta(seconds=61),
        )
        worker_service.heartbeat(
            principal,
            heartbeat,
            now=now + timedelta(seconds=62),
        )
        assert len(RecordingWebhookHandler.payloads) == 2
        assert "【设备恢复】" in json.dumps(
            RecordingWebhookHandler.payloads[1],
            ensure_ascii=False,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
