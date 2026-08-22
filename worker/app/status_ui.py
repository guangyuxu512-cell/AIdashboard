import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def get_worker_data_root() -> Path:
    configured = os.environ.get("ECOMMERCE_WORKER_DATA_ROOT")
    if configured:
        return Path(configured).resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return Path(".").resolve()
    return (Path(local_app_data) / "EcommerceAIWorker").resolve()


def read_runtime_status(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    import tkinter as tk
    from tkinter import ttk
    from tkinter.scrolledtext import ScrolledText

    data_root = get_worker_data_root()
    status_path = data_root / "runtime-status.json"
    log_directory = data_root / "logs"
    root = tk.Tk()
    root.title("电商 AI Worker")
    root.geometry("620x520")
    root.minsize(520, 420)

    frame = ttk.Frame(root, padding=16)
    frame.pack(fill="both", expand=True)
    title = ttk.Label(frame, text="电商 AI Worker", font=("Microsoft YaHei UI", 15, "bold"))
    title.pack(anchor="w", pady=(0, 12))

    labels: dict[str, ttk.Label] = {}
    fields = (
        ("device_id", "设备"),
        ("connection_status", "服务器"),
        ("worker_status", "Worker 状态"),
        ("skill_display_name", "当前任务"),
        ("provider", "执行器"),
        ("app_name", "影刀应用"),
        ("phase", "当前阶段"),
        ("latest_message", "当前步骤"),
        ("started_at", "开始时间"),
        ("duration", "运行时间"),
    )
    facts = ttk.Frame(frame)
    facts.pack(fill="x")
    for row, (key, caption) in enumerate(fields):
        ttk.Label(facts, text=caption, width=12).grid(
            row=row,
            column=0,
            sticky="nw",
            pady=3,
        )
        value_label = ttk.Label(facts, text="—")
        value_label.grid(row=row, column=1, sticky="nw", pady=3)
        labels[key] = value_label

    ttk.Label(frame, text="最近日志").pack(anchor="w", pady=(14, 6))
    logs = ScrolledText(frame, height=12, wrap="word", state="disabled")
    logs.pack(fill="both", expand=True)

    def refresh() -> None:
        state = read_runtime_status(status_path)
        for key, label in labels.items():
            value = state.get(key)
            if key == "connection_status":
                value = "已连接" if value == "connected" else "未连接"
            elif key == "worker_status":
                value = "运行中" if value == "running" else "已停止"
            elif key == "duration":
                started_at = state.get("started_at")
                if isinstance(started_at, str):
                    try:
                        started = datetime.fromisoformat(started_at)
                        seconds = max(
                            0,
                            int((datetime.now(UTC) - started).total_seconds()),
                        )
                        value = f"{seconds // 60} 分 {seconds % 60} 秒"
                    except ValueError:
                        value = None
            label.configure(text=str(value) if value else "—")
        recent = state.get("recent_events", [])
        lines = []
        if isinstance(recent, list):
            for event in recent[-50:]:
                if isinstance(event, dict):
                    lines.append(
                        f"{event.get('event_at', '')}  "
                        f"{event.get('level', '')}  {event.get('message', '')}",
                    )
        logs.configure(state="normal")
        logs.delete("1.0", "end")
        logs.insert("end", "\n".join(lines) if lines else "暂无运行日志")
        logs.configure(state="disabled")

    def open_logs() -> None:
        log_directory.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(log_directory)  # type: ignore[attr-defined]

    actions = ttk.Frame(frame)
    actions.pack(fill="x", pady=(12, 0))
    ttk.Button(actions, text="刷新", command=refresh).pack(side="left")
    ttk.Button(actions, text="打开日志目录", command=open_logs).pack(
        side="left",
        padx=8,
    )
    ttk.Button(actions, text="关闭窗口", command=root.destroy).pack(side="right")

    def refresh_periodically() -> None:
        refresh()
        root.after(1000, refresh_periodically)

    refresh_periodically()
    root.mainloop()
    return 0
