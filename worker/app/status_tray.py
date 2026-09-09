from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import Protocol


class TrayIcon(Protocol):
    def run_detached(self, setup: Callable[["TrayIcon"], None] | None = None) -> None: ...

    def stop(self) -> None: ...


TrayIconFactory = Callable[[Callable[[], None], Callable[[], None], Callable[[], None]], TrayIcon]


class WorkerStatusTray:
    """A deliberately small tray wrapper for the independently running Worker Core."""

    def __init__(
        self,
        *,
        on_open: Callable[[], None],
        on_open_logs: Callable[[], None],
        on_exit_status_ui: Callable[[], None],
        icon_factory: TrayIconFactory | None = None,
    ) -> None:
        self._on_open = on_open
        self._on_open_logs = on_open_logs
        self._on_exit_status_ui = on_exit_status_ui
        self._icon_factory = icon_factory or _create_tray_icon
        self._icon: TrayIcon | None = None

    @property
    def started(self) -> bool:
        return self._icon is not None

    def start(self) -> bool:
        if self._icon is not None:
            return True
        ready = Event()
        cancelled = Event()

        def setup(icon: TrayIcon) -> None:
            if cancelled.is_set():
                icon.stop()
                return
            setattr(icon, "visible", True)
            ready.set()

        try:
            icon = self._icon_factory(
                self._on_open,
                self._on_open_logs,
                self._on_exit_status_ui,
            )
            icon.run_detached(setup)
        except Exception:
            return False
        if not ready.wait(timeout=2):
            cancelled.set()
            return False
        self._icon = icon
        return True

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:
            # The status window must still be able to exit if Windows has already
            # removed its notification-area icon.
            pass
        finally:
            self._icon = None


def _create_tray_icon(
    on_open: Callable[[], None],
    on_open_logs: Callable[[], None],
    on_exit_status_ui: Callable[[], None],
) -> TrayIcon:
    from PIL import Image, ImageDraw
    import pystray

    image = Image.new("RGBA", (64, 64), (42, 91, 140, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((14, 14, 50, 50), fill=(255, 255, 255, 255))
    draw.rectangle((29, 22, 35, 42), fill=(42, 91, 140, 255))
    draw.rectangle((22, 29, 42, 35), fill=(42, 91, 140, 255))
    return pystray.Icon(
        "ecommerce-ai-worker",
        image,
        "电商 AI Worker",
        pystray.Menu(
            pystray.MenuItem("打开状态", lambda _icon, _item: on_open(), default=True),
            pystray.MenuItem("打开日志", lambda _icon, _item: on_open_logs()),
            pystray.MenuItem("退出状态界面", lambda _icon, _item: on_exit_status_ui()),
        ),
    )
