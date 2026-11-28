"""Local control window. Closing the window never stops the daemon."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from uuid import uuid4

import psutil

from app.local_config import WindowsDpapiTokenProtector
from siyu_guard.autostart import enable_autostart
from siyu_guard.guard import InstanceLock, no_window, peer_command
from siyu_guard.probes import collector_windows, sourcing_bootstrap
from siyu_guard.storage import data_root, load_config, read_json, write_json


KINDS = {"普通程序": "process", "任务型程序": "task_app", "Worker": "worker", "1688 采集": "sourcing", "比特浏览器": "bit",
         "Windows 服务": "service", "采集插件": "plugin"}


class Window:
    def __init__(self, root: tk.Tk, directory: Path):
        self.root, self.directory = root, directory
        root.title("思余软件守护")
        root.geometry("800x470")
        root.minsize(650, 350)
        bar = ttk.Frame(root, padding=12)
        bar.pack(fill="x")
        for label, command in (("添加", self.add), ("启用 / 暂停", self.toggle),
                               ("删除", self.remove), ("设置登录自启", self.autostart),
                               ("停止守护", self.stop_daemon)):
            ttk.Button(bar, text=label, command=command).pack(side="left", padx=(0, 8))
        frame = ttk.Frame(root, padding=(12, 0, 12, 12))
        frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(frame, columns=("name", "kind", "status"), show="headings", selectmode="browse")
        for column, title, width in (("name", "名称", 230), ("kind", "类型", 150), ("status", "状态", 350)):
            self.table.heading(column, text=title)
            self.table.column(column, width=width, anchor="w")
        scroll = ttk.Scrollbar(frame, command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.refresh()
        self.start_daemon()

    def start_daemon(self):
        try:
            (self.directory / "stopped").unlink(missing_ok=True)
            subprocess.Popen(peer_command("sentinel"), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, close_fds=True,
                             cwd=str(Path(__file__).resolve().parents[1]), creationflags=no_window())
        except OSError:
            messagebox.showerror("启动失败", "无法启动守护进程", parent=self.root)

    def stop_daemon(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "stopped").touch()

    def refresh(self):
        config = load_config(self.directory)
        status = read_json(self.directory / "status.json", {})
        fresh = (not (self.directory / "stopped").exists() and isinstance(status, dict)
                 and isinstance(status.get("updated_at"), (int, float))
                 and 0 <= time.time() - status["updated_at"] < 40)
        states = {row.get("id"): row.get("state") for row in status.get("items", [])} if fresh else {}
        selection = self.table.selection()
        for item in self.table.get_children():
            self.table.delete(item)
        for item in config.get("items", []):
            kind = next((label for label, value in KINDS.items() if value == item.get("kind")), "未知")
            state = "未启用" if not item.get("enabled") else states.get(item.get("id"), "守护未连接")
            self.table.insert("", "end", iid=item["id"], values=(item.get("name", ""), kind, state))
        if selection and self.table.exists(selection[0]):
            self.table.selection_set(selection[0])
        self.root.after(3000, self.refresh)

    def save(self, config):
        write_json(self.directory / "config.json", config)

    def add(self):
        Editor(self.root, self.save_new)

    def save_new(self, item):
        config = load_config(self.directory)
        config["items"].append(item)
        self.save(config)

    def _selected(self):
        selection = self.table.selection()
        return selection[0] if selection else None

    def toggle(self):
        selected = self._selected()
        config = load_config(self.directory)
        for item in config["items"]:
            if item.get("id") == selected:
                item["enabled"] = not item.get("enabled")
                self.save(config)
                break

    def remove(self):
        selected = self._selected()
        if not selected or not messagebox.askyesno("删除", "删除所选监控？", parent=self.root):
            return
        config = load_config(self.directory)
        config["items"] = [item for item in config["items"] if item.get("id") != selected]
        self.save(config)

    def autostart(self):
        try:
            enable_autostart()
        except (RuntimeError, OSError, subprocess.SubprocessError) as error:
            messagebox.showerror("设置失败", str(error), parent=self.root)
            return
        self.start_daemon()
        messagebox.showinfo("已设置", "登录 Windows 后自动守护", parent=self.root)


class Editor:
    def __init__(self, parent, callback):
        self.callback = callback
        self.window = tk.Toplevel(parent)
        self.window.title("添加监控")
        self.window.transient(parent)
        self.window.resizable(False, False)
        self.window.grab_set()
        self.values = {key: tk.StringVar() for key in ("name", "kind", "path", "data_root", "service", "url", "browser_id", "token")}
        self.values["kind"].set("普通程序")
        self.browser_options = {}
        self.service_options = {}
        self.restart = tk.BooleanVar(value=True)
        self.form = ttk.Frame(self.window, padding=16)
        self.form.pack(fill="both", expand=True)
        ttk.Label(self.form, text="名称").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(self.form, textvariable=self.values["name"], width=48).grid(row=0, column=1, sticky="ew")
        ttk.Label(self.form, text="类型").grid(row=1, column=0, sticky="w", pady=5)
        choice = ttk.Combobox(self.form, textvariable=self.values["kind"], values=list(KINDS), state="readonly")
        choice.grid(row=1, column=1, sticky="ew")
        choice.bind("<<ComboboxSelected>>", lambda _: self.fields())
        self.dynamic = ttk.Frame(self.form)
        self.dynamic.grid(row=2, column=0, columnspan=2, sticky="ew")
        buttons = ttk.Frame(self.form)
        buttons.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(buttons, text="取消", command=self.window.destroy).pack(side="left", padx=5)
        ttk.Button(buttons, text="保存", command=self.save).pack(side="left")
        self.fields()

    def fields(self):
        for widget in self.dynamic.winfo_children():
            widget.destroy()
        kind = KINDS[self.values["kind"].get()]
        if kind == "plugin":
            fields = (("运营中心地址", "url"), ("浏览器标识", "browser_id"), ("只读 Token", "token"))
        elif kind == "service":
            fields = (("服务名称", "service"),)
        elif kind == "worker":
            if not self.values["data_root"].get():
                self.values["data_root"].set(os.environ.get("ECOMMERCE_WORKER_DATA_ROOT") or
                                             str(Path(os.environ.get("LOCALAPPDATA", ".")) / "EcommerceAIWorker"))
            fields = (("程序路径", "path"), ("Worker 数据目录", "data_root"))
        else:
            fields = (("程序路径", "path"),)
        for row, (label, key) in enumerate(fields):
            ttk.Label(self.dynamic, text=label).grid(row=row, column=0, sticky="w", pady=5)
            if key == "browser_id":
                self.browser_choice = ttk.Combobox(self.dynamic, textvariable=self.values[key], width=42)
                self.browser_choice.grid(row=row, column=1, sticky="ew")
                ttk.Button(self.dynamic, text="读取窗口", command=self.load_windows).grid(row=row, column=2, padx=5)
            elif key == "service" and os.name == "nt":
                self.service_options = {}
                try:
                    for service in psutil.win_service_iter():
                        info = service.as_dict()
                        name, display = info.get("name"), info.get("display_name")
                        if name:
                            self.service_options[f"{display or name} · {name}"] = name
                except (psutil.Error, OSError):
                    pass
                ttk.Combobox(self.dynamic, textvariable=self.values[key], width=42,
                             values=sorted(self.service_options)).grid(row=row, column=1, sticky="ew")
            else:
                ttk.Entry(self.dynamic, textvariable=self.values[key], width=45,
                          show="*" if key == "token" else "").grid(row=row, column=1, sticky="ew")
            if key in ("path", "data_root"):
                ttk.Button(self.dynamic, text="选择", command=lambda field=key: self.choose(field)).grid(row=row, column=2, padx=5)
        if kind not in ("plugin", "task_app"):
            ttk.Checkbutton(self.dynamic, text="程序退出后自动启动", variable=self.restart).grid(
                row=len(fields), column=1, sticky="w", pady=5)

    def choose(self, field):
        path = (filedialog.askdirectory(parent=self.window) if field == "data_root" else
                filedialog.askopenfilename(parent=self.window, filetypes=[("程序", "*.exe")]))
        if path:
            self.values[field].set(path)

    def load_windows(self):
        url, token = self.values["url"].get().strip(), self.values["token"].get().strip()
        result = queue.Queue(maxsize=1)
        def run():
            try:
                result.put(collector_windows(url, token))
            except Exception:
                result.put((None, "读取异常"))
        threading.Thread(target=run, daemon=True).start()
        def finish():
            if not self.window.winfo_exists():
                return
            if not hasattr(self, "browser_choice") or not self.browser_choice.winfo_exists():
                return
            try:
                rows, error = result.get_nowait()
            except queue.Empty:
                self.window.after(100, finish)
                return
            if rows is None:
                messagebox.showerror("读取失败", error, parent=self.window)
                return
            self.browser_options = {}
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("browserId"), str):
                    continue
                browser_id = row["browserId"]
                label = f"{row.get('name') or '未命名'} · {browser_id}"
                self.browser_options[label] = browser_id
            self.browser_choice["values"] = list(self.browser_options)
            if self.browser_options:
                self.browser_choice.current(0)
            else:
                messagebox.showinfo("读取窗口", "没有采集窗口", parent=self.window)
        self.window.after(100, finish)

    def save(self):
        kind = KINDS[self.values["kind"].get()]
        name = self.values["name"].get().strip()
        item = {"id": str(uuid4()), "name": name, "kind": kind, "enabled": True,
                "restart": self.restart.get()}
        if kind == "plugin":
            url, selected, token = (self.values[k].get().strip() for k in ("url", "browser_id", "token"))
            browser_id = self.browser_options.get(selected, selected)
            if not url.startswith("https://") or not browser_id or not token:
                return self.invalid()
            item.update(url=url.rstrip("/"), browser_id=browser_id,
                        protected_token=WindowsDpapiTokenProtector().protect(token))
        elif kind == "service":
            selected = self.values["service"].get().strip()
            service = self.service_options.get(selected, selected)
            if not service or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for c in service):
                return self.invalid()
            item["service"] = service
        else:
            path = Path(self.values["path"].get().strip())
            if not path.is_absolute() or not path.is_file() or path.suffix.lower() != ".exe":
                return self.invalid()
            item["path"] = sourcing_bootstrap(str(path)) if kind == "sourcing" else str(path.resolve())
            if kind == "worker":
                directory = Path(self.values["data_root"].get().strip())
                if not directory.is_absolute():
                    return self.invalid()
                item["data_root"] = str(directory.resolve())
        if not name:
            return self.invalid()
        self.callback(item)
        self.window.destroy()

    def invalid(self):
        messagebox.showerror("信息不完整", "请检查填写内容", parent=self.window)


def main():
    directory = data_root()
    with InstanceLock(directory, "window.lock") as acquired:
        if not acquired:
            return
        root = tk.Tk()
        Window(root, directory)
        root.mainloop()
