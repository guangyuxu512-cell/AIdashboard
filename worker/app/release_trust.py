"""Read the public trust anchor packaged at Worker release time."""
import base64
from pathlib import Path
import sys


def packaged_capability_public_key() -> bytes | None:
    bundle = getattr(sys, "_MEIPASS", None)
    if not bundle:
        return None
    try:
        path = Path(bundle) / "capability-public-key.txt"
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 256:
            return None
        key = base64.b64decode(path.read_text(encoding="ascii").strip(), validate=True)
        return key if len(key) == 32 else None
    except (OSError, ValueError, UnicodeError):
        return None
