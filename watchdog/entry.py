"""PyInstaller entry point for the GUI and the independent daemon."""
import sys

if sys.argv[1:] == ["--self-check"]:
    import httpx
    import psutil
    import tkinter
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from app.local_config import WindowsDpapiTokenProtector
    from siyu_guard.guard import Guard
    assert httpx and psutil and tkinter and Ed25519PublicKey and WindowsDpapiTokenProtector and Guard
    raise SystemExit(0)

if sys.argv[1:] == ["--daemon"]:
    from siyu_guard.guard import daemon
    from siyu_guard.storage import data_root
    raise SystemExit(daemon(data_root()))

if sys.argv[1:] == ["--sentinel"]:
    from siyu_guard.guard import sentinel
    from siyu_guard.storage import data_root
    raise SystemExit(sentinel(data_root()))

from siyu_guard.ui import main
main()
