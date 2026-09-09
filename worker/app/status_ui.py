import json
import os
from dataclasses import dataclass
from queue import Empty, SimpleQueue
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.local_config import (
    DEFAULT_PRODUCTION_SERVER_URL,
    LocalInputPaths,
    LocalWorkerConfig,
    WorkerConfigService,
    WorkerConfigurationError,
    get_default_local_input_paths,
    get_worker_data_root,
    inspect_local_input_paths,
)
from app.process_control import WorkerProcessController, WorkerProcessInfo
from app.providers.yingdao import WindowsYingdaoRuntimeLocator, YingdaoSessionError
from app.provisioning import ConnectionTestResult, WorkerProvisioningClient
from app.status_tray import WorkerStatusTray
from app.version import WORKER_VERSION


_HEARTBEAT_FRESHNESS_SECONDS = 45
_CORE_STATUS_FRESHNESS_SECONDS = 90


@dataclass(frozen=True)
class WorkerConfigurationApplyResult:
    config: LocalWorkerConfig
    core_running: bool


def apply_provisioned_worker_configuration(
    *,
    config_service: WorkerConfigService,
    process_controller: WorkerProcessController,
    current_task_id: object | None,
    server_url: str,
    device_id: UUID,
    device_token: str,
    device_display_name: str | None,
    yingdao_install_root: Path | None,
    yingdao_data_root: Path | None,
    yingdao_test_app_id: str | None,
    params_json_path: Path,
    account_json_path: Path,
    images_dir: Path,
) -> WorkerConfigurationApplyResult:
    """Apply a provisioned identity without leaving an old Core authenticated.

    Provisioning establishes the device identity; this function only switches the
    local Core while it is idle.  It intentionally does not claim distributed
    atomicity with the backend: a failed stop leaves the old configuration intact,
    and a failed new start leaves the Core stopped instead of reviving the old
    identity.
    """
    if current_task_id:
        raise WorkerConfigurationError(
            "当前任务正在运行；请等待任务结束后再保存配置，避免中断执行",
        )

    previous_core = process_controller.running()
    if previous_core is not None and not process_controller.stop():
        raise WorkerConfigurationError(
            "现有 Worker 未能停止；未保存新的设备身份",
        )

    config = config_service.save(
        server_url=server_url,
        device_id=device_id,
        device_token=device_token,
        device_display_name=device_display_name,
        yingdao_install_root=yingdao_install_root,
        yingdao_data_root=yingdao_data_root,
        yingdao_test_app_id=yingdao_test_app_id,
        params_json_path=params_json_path,
        account_json_path=account_json_path,
        images_dir=images_dir,
    )
    running = process_controller.start()
    if running is not None and running.device_id != config.device_id:
        # A stale Core must never keep sending heartbeats under a replaced config.
        process_controller.stop()
        running = None
    return WorkerConfigurationApplyResult(config=config, core_running=running is not None)


def read_runtime_status(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def should_open_configuration(config: LocalWorkerConfig | None) -> bool:
    return config is None


def main() -> int:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    data_root = get_worker_data_root()
    try:
        config_service = WorkerConfigService(data_root)
        config = config_service.load() if config_service.exists() else None
    except WorkerConfigurationError:
        config = None
        config_service = WorkerConfigService(data_root)
    process_controller = WorkerProcessController(data_root)
    if config is not None and process_controller.running() is None:
        process_controller.start()

    status_path = data_root / "runtime-status.json"
    log_directory = data_root / "logs"
    provisioning_client = WorkerProvisioningClient()

    root = tk.Tk()
    root.title("电商 AI Worker")
    root.geometry("800x720")
    root.minsize(720, 620)

    tray_actions: SimpleQueue[str] = SimpleQueue()

    def restore_status_window() -> None:
        root.deiconify()
        root.state("normal")
        root.lift()
        root.focus_force()

    def queue_tray_action(action: str) -> None:
        tray_actions.put(action)

    status_tray = WorkerStatusTray(
        on_open=lambda: queue_tray_action("open"),
        on_open_logs=lambda: queue_tray_action("logs"),
        on_exit_status_ui=lambda: queue_tray_action("exit"),
    )

    def hide_to_tray() -> None:
        if status_tray.start():
            root.withdraw()
            return
        # A Worker must remain operable even if the Windows tray is unavailable.
        restore_status_window()

    def hide_after_minimize() -> None:
        if root.winfo_exists() and root.state() == "iconic":
            hide_to_tray()

    def on_root_unmap(event: Any) -> None:
        if event.widget is root:
            root.after_idle(hide_after_minimize)

    root.bind("<Unmap>", on_root_unmap)
    root.protocol("WM_DELETE_WINDOW", hide_to_tray)

    outer = ttk.Frame(root, padding=16)
    outer.pack(fill="both", expand=True)
    ttk.Label(
        outer,
        text="电商 AI Worker",
        font=("Microsoft YaHei UI", 15, "bold"),
    ).pack(anchor="w", pady=(0, 10))

    notebook = ttk.Notebook(outer)
    notebook.pack(fill="both", expand=True)
    status_tab = ttk.Frame(notebook, padding=14)
    config_tab = ttk.Frame(notebook, padding=14)
    diagnostic_tab = ttk.Frame(notebook, padding=14)
    notebook.add(status_tab, text="状态")
    notebook.add(config_tab, text="配置")
    notebook.add(diagnostic_tab, text="诊断")

    status_labels: dict[str, ttk.Label] = {}
    status_fields = (
        ("device_display_name", "设备"),
        ("device_id", "Device ID"),
        ("worker_version", "Worker 版本"),
        ("connection_status", "服务器"),
        ("last_heartbeat", "最后心跳"),
        ("worker_status", "Worker"),
        ("provider_status", "ShadowBot 状态"),
        ("provider_version", "ShadowBot 版本"),
        ("provider_account", "账号"),
        ("provider_application_count", "云端应用"),
        ("business_skill_count", "业务 Skill"),
        ("current_task", "当前任务"),
        ("duration", "运行时间"),
    )
    facts = ttk.Frame(status_tab)
    facts.pack(fill="x")
    facts.columnconfigure(1, weight=1)
    for row, (key, caption) in enumerate(status_fields):
        ttk.Label(facts, text=caption, width=18).grid(
            row=row,
            column=0,
            sticky="nw",
            pady=3,
        )
        label = ttk.Label(facts, text="—")
        label.grid(row=row, column=1, sticky="nw", pady=3)
        status_labels[key] = label

    ttk.Label(status_tab, text="最近日志").pack(anchor="w", pady=(14, 6))
    logs = ScrolledText(status_tab, height=11, wrap="word", state="disabled")
    logs.pack(fill="both", expand=True)

    configured_server_url = config.server_url if config else DEFAULT_PRODUCTION_SERVER_URL
    token_var = tk.StringVar(
        value=config.device_token.get_secret_value() if config else "",
    )
    device_id_var = tk.StringVar(value=str(config.device_id) if config else "")
    device_name_var = tk.StringVar(
        value=(config.device_display_name or "") if config else "",
    )
    shadowbot_var = tk.StringVar(value="")
    default_local_inputs = get_default_local_input_paths(config_service.data_root)
    params_json_var = tk.StringVar(
        value=str(
            config.params_json_path
            if config is not None
            else default_local_inputs.params_json_path
        ),
    )
    account_json_var = tk.StringVar(
        value=str(
            config.account_json_path
            if config is not None
            else default_local_inputs.account_json_path
        ),
    )
    images_dir_var = tk.StringVar(
        value=str(
            config.images_dir
            if config is not None
            else default_local_inputs.images_dir
        ),
    )
    config_result_var = tk.StringVar(
        value="已读取现有配置" if config else "等待首次配置",
    )
    token_revealed = tk.BooleanVar(value=False)
    selected_shadowbot: Path | None = None

    config_form = ttk.Frame(config_tab)
    config_form.pack(fill="x")
    config_form.columnconfigure(1, weight=1)

    def add_config_row(row: int, caption: str, widget: Any) -> None:
        ttk.Label(config_form, text=caption, width=22).grid(
            row=row,
            column=0,
            sticky="w",
            pady=6,
        )
        widget.grid(row=row, column=1, sticky="ew", pady=6)

    add_config_row(
        0,
        "服务器",
        ttk.Label(config_form, text="由发行包统一配置；连接状态见“状态”页"),
    )
    token_frame = ttk.Frame(config_form)
    token_frame.columnconfigure(0, weight=1)
    token_entry = ttk.Entry(token_frame, textvariable=token_var, show="•")
    token_entry.grid(row=0, column=0, sticky="ew")

    def toggle_token() -> None:
        token_revealed.set(not token_revealed.get())
        token_entry.configure(show="" if token_revealed.get() else "•")
        token_toggle.configure(text="隐藏" if token_revealed.get() else "显示")

    token_toggle = ttk.Button(token_frame, text="显示", command=toggle_token)
    token_toggle.grid(row=0, column=1, padx=(8, 0))
    add_config_row(1, "Worker Token", token_frame)
    add_config_row(
        2,
        "Device ID（只读）",
        ttk.Entry(config_form, textvariable=device_id_var, state="readonly"),
    )
    add_config_row(
        3,
        "设备名称",
        ttk.Entry(config_form, textvariable=device_name_var, state="readonly"),
    )
    shadowbot_frame = ttk.Frame(config_form)
    shadowbot_frame.columnconfigure(0, weight=1)
    ttk.Entry(
        shadowbot_frame,
        textvariable=shadowbot_var,
        state="readonly",
    ).grid(row=0, column=0, sticky="ew")
    add_config_row(4, "ShadowBot 6.3.6", shadowbot_frame)

    local_input_frame = ttk.LabelFrame(config_tab, text="本地输入", padding=10)
    local_input_frame.pack(fill="x", pady=(12, 0))
    local_input_frame.columnconfigure(1, weight=1)
    local_input_buttons: list[ttk.Button] = []

    def add_local_input_row(
        row: int,
        caption: str,
        variable: Any,
        command: Any,
    ) -> None:
        ttk.Label(local_input_frame, text=caption, width=20).grid(
            row=row,
            column=0,
            sticky="w",
            pady=5,
        )
        ttk.Entry(local_input_frame, textvariable=variable).grid(
            row=row,
            column=1,
            sticky="ew",
            pady=5,
        )
        button = ttk.Button(local_input_frame, text="选择", command=command)
        button.grid(row=row, column=2, padx=(8, 0), pady=5)
        local_input_buttons.append(button)

    def choose_json_path(variable: Any, title: str) -> None:
        current = Path(variable.get().strip())
        selected = filedialog.asksaveasfilename(
            title=title,
            initialdir=str(current.parent),
            initialfile=current.name,
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("所有文件", "*.*")],
        )
        if selected:
            variable.set(selected)

    def choose_images_directory() -> None:
        selected = filedialog.askdirectory(
            title="选择图片工作目录",
            initialdir=images_dir_var.get().strip(),
        )
        if selected:
            images_dir_var.set(selected)

    add_local_input_row(
        0,
        "参数 JSON",
        params_json_var,
        lambda: choose_json_path(params_json_var, "选择参数 JSON 路径"),
    )
    add_local_input_row(
        1,
        "账号 JSON",
        account_json_var,
        lambda: choose_json_path(account_json_var, "选择账号 JSON 路径"),
    )
    add_local_input_row(
        2,
        "图片工作目录",
        images_dir_var,
        choose_images_directory,
    )
    ttk.Label(
        config_tab,
        textvariable=config_result_var,
        wraplength=650,
    ).pack(fill="x", pady=(12, 8))

    action_frame = ttk.Frame(config_tab)
    action_frame.pack(fill="x")
    test_button = ttk.Button(action_frame, text="测试连接")
    test_button.pack(side="left")
    save_button = ttk.Button(action_frame, text="保存并启动")
    save_button.pack(side="left", padx=8)
    detect_button = ttk.Button(action_frame, text="重新检测")
    detect_button.pack(side="left")
    choose_button = ttk.Button(action_frame, text="选择路径")
    choose_button.pack(side="left", padx=8)

    diagnostic_labels: dict[str, ttk.Label] = {}
    diagnostic_fields = (
        ("backend", "Backend"),
        ("token", "Worker Token"),
        ("heartbeat", "Heartbeat"),
        ("skills", "Skill Capability"),
        ("process", "ShadowBot 进程"),
        ("version", "ShadowBot 版本"),
        ("session", "ShadowBot Session"),
        ("applications", "云端应用"),
        ("provider_refresh", "最近 Provider 刷新"),
        ("params_json", "参数 JSON"),
        ("account_json", "账号 JSON"),
        ("images_dir", "图片工作目录"),
    )
    diagnostic_facts = ttk.Frame(diagnostic_tab)
    diagnostic_facts.pack(fill="x")
    diagnostic_facts.columnconfigure(1, weight=1)
    for row, (key, caption) in enumerate(diagnostic_fields):
        ttk.Label(diagnostic_facts, text=caption, width=22).grid(
            row=row,
            column=0,
            sticky="nw",
            pady=5,
        )
        label = ttk.Label(diagnostic_facts, text="—")
        label.grid(row=row, column=1, sticky="nw", pady=5)
        diagnostic_labels[key] = label

    diagnostic_actions = ttk.Frame(diagnostic_tab)
    diagnostic_actions.pack(fill="x", pady=(14, 0))

    def open_logs() -> None:
        log_directory.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(log_directory)  # type: ignore[attr-defined]

    ttk.Button(
        diagnostic_actions,
        text="重新检测",
        command=lambda: detect_shadowbot(),
    ).pack(side="left")
    ttk.Button(
        diagnostic_actions,
        text="打开日志目录",
        command=open_logs,
    ).pack(side="left", padx=8)

    def set_busy(busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for button in (
            test_button,
            save_button,
            detect_button,
            choose_button,
            *local_input_buttons,
        ):
            button.configure(state=state)

    def configured_locator() -> WindowsYingdaoRuntimeLocator:
        root_path = None
        if selected_shadowbot is not None:
            root_path = selected_shadowbot.parent
        elif config is not None:
            root_path = config.yingdao_install_root
        return WindowsYingdaoRuntimeLocator(root_path)

    def detect_shadowbot() -> None:
        set_busy(True)
        shadowbot_var.set("正在检测…")

        def work() -> None:
            executable = configured_locator().find_supported_executable()

            def finish() -> None:
                nonlocal selected_shadowbot
                selected_shadowbot = executable
                shadowbot_var.set(
                    str(executable)
                    if executable is not None
                    else "未检测到 ShadowBot 6.3.6"
                )
                set_busy(False)

            root.after(0, finish)

        threading.Thread(target=work, daemon=True).start()

    def choose_shadowbot() -> None:
        nonlocal selected_shadowbot
        selected = filedialog.askopenfilename(
            title="选择 ShadowBot 6.3.6",
            filetypes=[("ShadowBot", "ShadowBot*.exe"), ("EXE", "*.exe")],
        )
        if not selected:
            return
        try:
            selected_shadowbot = WindowsYingdaoRuntimeLocator(
                Path(selected).parent,
            ).validate_supported_executable(Path(selected))
        except YingdaoSessionError as error:
            selected_shadowbot = None
            shadowbot_var.set("版本不支持")
            messagebox.showerror("ShadowBot 路径无效", error.message)
            return
        shadowbot_var.set(str(selected_shadowbot))

    def test_connection(*, save_after: bool = False) -> None:
        set_busy(True)
        config_result_var.set("正在测试服务器与 Worker Token…")
        token = token_var.get().strip()

        def work() -> None:
            result = provisioning_client.test(configured_server_url, token)

            def finish() -> None:
                config_result_var.set(f"{result.message}（{result.code}）")
                if result.identity is not None:
                    device_id_var.set(str(result.identity.device_id))
                    device_name_var.set(result.identity.device_display_name)
                set_busy(False)
                if save_after:
                    save_configuration(result)

            root.after(0, finish)

        threading.Thread(target=work, daemon=True).start()

    def save_configuration(result: ConnectionTestResult | None = None) -> None:
        nonlocal config
        if result is None:
            test_connection(save_after=True)
            return
        if not result.ok or result.identity is None:
            if (
                config is not None
                and result.code in {"BACKEND_UNREACHABLE", "BACKEND_TIMEOUT", "TLS_FAILED"}
                and configured_server_url.rstrip("/") == config.server_url
                and token_var.get() == config.device_token.get_secret_value()
                and messagebox.askyesno(
                    "服务器暂时不可达",
                    "现有设备身份和 Token 未变。是否仅保存本机 ShadowBot 路径？",
                )
            ):
                identity_device_id = config.device_id
                identity_name = config.device_display_name
            else:
                return
        else:
            identity_device_id = result.identity.device_id
            identity_name = result.identity.device_display_name
        try:
            applied = apply_provisioned_worker_configuration(
                config_service=config_service,
                process_controller=process_controller,
                current_task_id=read_runtime_status(status_path).get("current_task_id"),
                server_url=configured_server_url,
                device_id=identity_device_id,
                device_token=token_var.get(),
                device_display_name=identity_name,
                yingdao_install_root=(
                    selected_shadowbot.parent
                    if selected_shadowbot is not None
                    else (config.yingdao_install_root if config else None)
                ),
                yingdao_data_root=config.yingdao_data_root if config else None,
                yingdao_test_app_id=config.yingdao_test_app_id if config else None,
                params_json_path=_required_path(
                    params_json_var.get(),
                    "参数 JSON 路径",
                ),
                account_json_path=_required_path(
                    account_json_var.get(),
                    "账号 JSON 路径",
                ),
                images_dir=_required_path(
                    images_dir_var.get(),
                    "图片工作目录",
                ),
            )
        except (OSError, WorkerConfigurationError) as error:
            config_result_var.set(f"配置保存失败：{error}")
            return
        config = applied.config
        device_id_var.set(str(config.device_id))
        device_name_var.set(config.device_display_name or "")
        config_result_var.set(
            "配置已保存，Worker 已启动"
            if applied.core_running
            else "配置已保存，但 Worker 未能以新身份启动；旧 Core 已停止，请查看日志"
        )
        notebook.select(status_tab)

    test_button.configure(command=test_connection)
    save_button.configure(command=save_configuration)
    detect_button.configure(command=detect_shadowbot)
    choose_button.configure(command=choose_shadowbot)

    def refresh() -> None:
        state = read_runtime_status(status_path)
        running = process_controller.running() is not None
        rendered = _render_status(state, running=running)
        for key, label in status_labels.items():
            label.configure(text=rendered.get(key, "—"))
        recent = state.get("recent_events", [])
        lines: list[str] = []
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
        local_inputs = (
            LocalInputPaths(
                params_json_path=config.params_json_path,
                account_json_path=config.account_json_path,
                images_dir=config.images_dir,
            )
            if config is not None
            else default_local_inputs
        )
        diagnostics = _render_diagnostics(
            state,
            running=running,
            local_inputs=inspect_local_input_paths(local_inputs),
        )
        for key, label in diagnostic_labels.items():
            label.configure(text=diagnostics.get(key, "—"))

    def refresh_periodically() -> None:
        while True:
            try:
                action = tray_actions.get_nowait()
            except Empty:
                break
            if action == "open":
                restore_status_window()
            elif action == "logs":
                open_logs()
            elif action == "exit":
                status_tray.stop()
                root.destroy()
                return
        refresh()
        root.after(1000, refresh_periodically)

    detect_shadowbot()
    if should_open_configuration(config):
        notebook.select(config_tab)
    refresh_periodically()
    root.mainloop()
    return 0


def _render_status(
    state: dict[str, Any],
    *,
    running: bool,
    now: datetime | None = None,
) -> dict[str, str]:
    observed_at = now or datetime.now(UTC)
    current_task = state.get("app_name") or state.get("skill_display_name") or "空闲"
    if state.get("current_task_id"):
        current_task = f"{current_task} · 执行中"
    return {
        "device_display_name": str(state.get("device_display_name") or "—"),
        "device_id": str(state.get("device_id") or "—"),
        "worker_version": str(state.get("worker_version") or WORKER_VERSION),
        "connection_status": (
            "已连接" if _backend_is_healthy(state, observed_at) else "连接异常"
        ),
        "last_heartbeat": _relative_time(
            state.get("last_heartbeat_at"),
            observed_at,
        ),
        "worker_status": _worker_status_label(state, running, observed_at),
        "provider_status": _provider_status_label(state.get("provider_status")),
        "provider_version": str(state.get("provider_version") or "—"),
        "provider_account": str(state.get("provider_account") or "—"),
        "provider_application_count": str(
            state.get("provider_application_count")
            if state.get("provider_application_count") is not None
            else "—"
        ),
        "business_skill_count": (
            str(state.get("business_skill_count", 0))
            if state.get("skill_sync_status") == "synced"
            else "未同步"
        ),
        "current_task": str(current_task),
        "duration": _duration(state.get("started_at")),
    }


def _render_diagnostics(
    state: dict[str, Any],
    *,
    running: bool,
    local_inputs: dict[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, str]:
    observed_at = now or datetime.now(UTC)
    provider_status = state.get("provider_status")
    heartbeat_healthy = _backend_is_healthy(state, observed_at)
    heartbeat_age = _relative_time(state.get("last_heartbeat_at"), observed_at)
    diagnostics = {
        "backend": "正常" if heartbeat_healthy else "异常",
        "token": {
            "valid": "有效",
            "invalid": "无效",
            "configured": "已配置 / 待验证",
        }.get(str(state.get("token_status")), "未配置"),
        "heartbeat": (
            f"正常 · {heartbeat_age}"
            if heartbeat_healthy
            else (
                f"已过期 · {heartbeat_age}"
                if heartbeat_age != "—"
                else "异常"
            )
        ),
        "skills": (
            "已同步" if state.get("skill_sync_status") == "synced" else "未同步"
        ),
        "process": {
            "运行中": "正常",
            "状态异常": "状态异常",
            "已停止": "未运行",
        }[_worker_status_label(state, running, observed_at)],
        "version": str(state.get("provider_version") or "—"),
        "session": "已登录" if provider_status == "ready" else _provider_status_label(provider_status),
        "applications": str(
            state.get("provider_application_count")
            if state.get("provider_application_count") is not None
            else "—"
        ),
        "provider_refresh": str(state.get("provider_refreshed_at") or "—"),
    }
    diagnostics.update(local_inputs or {})
    return diagnostics


def _required_path(value: str, caption: str) -> Path:
    path = value.strip()
    if not path:
        raise WorkerConfigurationError(f"{caption}不能为空")
    return Path(path)


def _provider_status_label(value: object) -> str:
    return {
        "ready": "已就绪",
        "not_installed": "未安装",
        "need_login": "需要登录",
        "version_unsupported": "版本不支持",
        "interface_unreachable": "接口不可用",
        "starting": "正在启动",
    }.get(str(value), "未检测")


def _backend_is_healthy(state: dict[str, Any], now: datetime) -> bool:
    if state.get("token_status") == "invalid":
        return False
    age = _seconds_since(state.get("last_heartbeat_at"), now)
    return age is not None and age <= _HEARTBEAT_FRESHNESS_SECONDS


def _worker_status_label(
    state: dict[str, Any],
    running: bool,
    now: datetime,
) -> str:
    if not running:
        return "已停止"
    age = _seconds_since(state.get("updated_at"), now)
    if age is None or age > _CORE_STATUS_FRESHNESS_SECONDS:
        return "状态异常"
    return "运行中"


def _relative_time(value: object, now: datetime) -> str:
    seconds = _seconds_since(value, now)
    if seconds is None:
        return "—"
    if seconds < 5:
        return "刚刚"
    if seconds < 60:
        return f"{int(seconds)} 秒前"
    if seconds < 3600:
        return f"{int(seconds // 60)} 分钟前"
    if seconds < 86400:
        return f"{int(seconds // 3600)} 小时前"
    return f"{int(seconds // 86400)} 天前"


def _seconds_since(value: object, now: datetime) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        observed_at = datetime.fromisoformat(value)
    except ValueError:
        return None
    if observed_at.tzinfo is None:
        return None
    return max(0.0, (now - observed_at).total_seconds())


def _duration(value: object) -> str:
    if not isinstance(value, str):
        return "—"
    try:
        started = datetime.fromisoformat(value)
    except ValueError:
        return "—"
    seconds = max(0, int((datetime.now(UTC) - started).total_seconds()))
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"
