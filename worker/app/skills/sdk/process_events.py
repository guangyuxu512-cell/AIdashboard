from __future__ import annotations

import sys
from typing import TextIO

from app.contracts import RuntimeEvent


PROCESS_EVENT_PREFIX = "__CCW_SKILL_EVENT__:"


class ProcessRuntimeEventWriter:
    """Serialize child-process SDK events without exposing Backend transport."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdout

    def __call__(self, event: RuntimeEvent) -> None:
        self.stream.write(f"{PROCESS_EVENT_PREFIX}{event.model_dump_json()}\n")
        self.stream.flush()


def decode_process_event_line(line: bytes) -> RuntimeEvent | None:
    prefix = PROCESS_EVENT_PREFIX.encode("ascii")
    if not line.startswith(prefix):
        return None
    return RuntimeEvent.model_validate_json(line[len(prefix) :].strip())
