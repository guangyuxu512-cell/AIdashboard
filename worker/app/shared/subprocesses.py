import subprocess
import sys
from collections.abc import Sequence
from os import PathLike
from typing import Any


_IS_WINDOWS = sys.platform == "win32"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def run_noninteractive_command(
    args: Sequence[str | PathLike[str]],
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    """Run a background helper CLI without creating a visible Windows console."""
    options = dict(kwargs)
    options["shell"] = False
    if _IS_WINDOWS:
        options["creationflags"] = (
            int(options.get("creationflags", 0)) | _CREATE_NO_WINDOW
        )
    return subprocess.run(args, **options)
