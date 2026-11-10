"""Durable terminal delivery; a result is removed only after an acknowledgement.

This file never stores task inputs, account payloads, or a platform Session.  A
task may run only once: failed delivery causes the stored terminal result to be
sent again, not the task to be executed again.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator


_SENSITIVE_KEYS = frozenset(
    {
        "account", "accounts", "authorization", "cookie", "cookies",
        "login_identifier", "password", "preferred_verification_channel",
        "secret", "token", "登录账号", "登录密码", "店铺列表",
    },
)


class OutboxError(RuntimeError):
    """An untrusted, conflicting or unreadable outbox item; preserve it."""


class TerminalDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal[1] = 1
    task_id: UUID
    skill_id: str
    status: Literal["success", "failed"]
    result: dict[str, Any] | None = None
    provider_inventory: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_terminal(self) -> TerminalDelivery:
        if not self.skill_id:
            raise ValueError("skill id is required")
        if self.status == "success" and (self.error_code or self.error_message):
            raise ValueError("success cannot carry a failure")
        if self.status == "failed" and (not self.error_code or not self.error_message):
            raise ValueError("failure requires a safe code and message")
        _reject_sensitive_keys(self.result)
        _reject_sensitive_keys(self.provider_inventory)
        return self


def _reject_sensitive_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _SENSITIVE_KEYS and child != "[REDACTED]":
                raise ValueError("terminal result contains a sensitive field")
            _reject_sensitive_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_sensitive_keys(child)


class ResultOutbox:
    """Store one immutable terminal per task inside the Worker data directory."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, task_id: UUID) -> Path:
        return self.root / f"{task_id}.json"

    def store(self, item: TerminalDelivery) -> None:
        self._write(item, previous=None)

    def replace_inventory_failure(self, item: TerminalDelivery) -> TerminalDelivery:
        """Preserve the existing discovery failure behavior without losing results."""
        if item.status != "success" or item.provider_inventory is None:
            raise OutboxError("terminal has no provider report")
        replacement = TerminalDelivery(
            task_id=item.task_id, skill_id=item.skill_id, status="failed",
            error_code="PROVIDER_INVENTORY_REPORT_FAILED",
            error_message="Provider inventory could not be saved",
        )
        self._write(replacement, previous=item)
        return replacement

    def _write(self, item: TerminalDelivery, *, previous: TerminalDelivery | None) -> None:
        payload = json.dumps(
            item.model_dump(mode="json"), ensure_ascii=False,
            separators=(",", ":"), sort_keys=True, allow_nan=False,
        ).encode("utf-8")
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = self._path(item.task_id)
        if path.exists():
            try:
                existing = TerminalDelivery.model_validate_json(path.read_bytes())
            except (OSError, ValueError) as error:
                raise OutboxError("terminal result is unreadable") from error
            if previous is not None:
                if existing != previous:
                    raise OutboxError("terminal result changed before replacement")
            elif existing != item:
                raise OutboxError("terminal result conflicts with existing result")
            else:
                return
        elif previous is not None:
            raise OutboxError("terminal result missing before replacement")
        name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=self.root, prefix=".terminal-", suffix=".tmp", delete=False,
            ) as output:
                name = output.name
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            # The Worker has a device-level single-instance lock.  No other
            # process may author the same device's outbox concurrently.
            os.replace(name, path)
            name = None
        finally:
            if name is not None:
                Path(name).unlink(missing_ok=True)

    def pending(self) -> list[TerminalDelivery]:
        if not self.root.exists():
            return []
        result: list[TerminalDelivery] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                item = TerminalDelivery.model_validate_json(path.read_bytes())
                if path.name != f"{item.task_id}.json":
                    raise ValueError("outbox name does not match task id")
            except (OSError, ValueError) as error:
                raise OutboxError("terminal result is unreadable") from error
            result.append(item)
        return result

    def acknowledge(self, item: TerminalDelivery) -> None:
        path = self._path(item.task_id)
        try:
            current = TerminalDelivery.model_validate_json(path.read_bytes())
        except FileNotFoundError:
            return
        except (OSError, ValueError) as error:
            raise OutboxError("terminal result is unreadable") from error
        if current != item:
            raise OutboxError("terminal result changed before acknowledgement")
        path.unlink()

    def reject(self, item: TerminalDelivery) -> None:
        """Keep an explicitly rejected result for local inspection, not retry."""
        path = self._path(item.task_id)
        try:
            current = TerminalDelivery.model_validate_json(path.read_bytes())
        except (OSError, ValueError) as error:
            raise OutboxError("terminal result is unreadable") from error
        if current != item:
            raise OutboxError("terminal result changed before rejection")
        rejected = self.root / "rejected"
        rejected.mkdir(mode=0o700, exist_ok=True)
        target = rejected / path.name
        if target.exists():
            raise OutboxError("rejected terminal already exists")
        os.replace(path, target)
