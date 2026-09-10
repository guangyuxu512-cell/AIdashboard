from app.status_tray import WorkerStatusTray


class FakeIcon:
    def __init__(self, *, fail_on_start: bool = False) -> None:
        self.fail_on_start = fail_on_start
        self.started = 0
        self.stopped = 0

    def run_detached(self, setup: object = None) -> None:
        self.started += 1
        if self.fail_on_start:
            raise RuntimeError("notification area unavailable")
        if callable(setup):
            setup(self)

    def stop(self) -> None:
        self.stopped += 1


def test_status_tray_starts_once_without_managing_worker_core() -> None:
    calls: list[str] = []
    icon = FakeIcon()
    tray = WorkerStatusTray(
        on_open=lambda: calls.append("open"),
        on_open_logs=lambda: calls.append("logs"),
        on_exit_status_ui=lambda: calls.append("exit"),
        icon_factory=lambda _open, _logs, _exit: icon,
    )

    assert tray.start() is True
    assert tray.start() is True
    assert icon.started == 1
    assert tray.started is True
    assert calls == []

    tray.stop()
    assert icon.stopped == 1
    assert tray.started is False


def test_status_tray_reports_initialization_failure_for_visible_ui_fallback() -> None:
    tray = WorkerStatusTray(
        on_open=lambda: None,
        on_open_logs=lambda: None,
        on_exit_status_ui=lambda: None,
        icon_factory=lambda _open, _logs, _exit: FakeIcon(fail_on_start=True),
    )

    assert tray.start() is False
    assert tray.started is False
