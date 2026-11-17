import sys

if len(sys.argv) == 3 and sys.argv[1] == "--check-version":
    from app.version import WORKER_VERSION
    raise SystemExit(0 if sys.argv[2] == WORKER_VERSION else 1)

if len(sys.argv) > 1 and sys.argv[1] == "--check-capability-trust":
    from app.release_trust import packaged_capability_public_key
    raise SystemExit(0 if packaged_capability_public_key() is not None else 2)

if len(sys.argv) == 3 and sys.argv[1] == "--check-active-worker":
    from pathlib import Path
    from app.base_updates import BaseUpdater
    from app.local_config import get_worker_data_root
    from app.release_trust import packaged_capability_public_key
    from app.version import WORKER_VERSION
    try:
        key = packaged_capability_public_key()
        if key is None:
            raise ValueError("missing release trust")
        release = BaseUpdater(get_worker_data_root() / "runtime" / "base-releases", key, WORKER_VERSION).active_release()
        raise SystemExit(0 if release is not None and release.executable.resolve() == Path(sys.argv[2]).resolve() else 1)
    except Exception:
        raise SystemExit(2) from None

if len(sys.argv) == 3 and sys.argv[1] == "--worker-update-helper":
    from app.base_update_handoff import apply_handoff
    from app.base_updates import BaseUpdater
    from app.config import get_settings
    from app.release_trust import packaged_capability_public_key
    from app.version import WORKER_VERSION
    try:
        key = packaged_capability_public_key()
        if key is None:
            raise ValueError("missing release trust")
        updater = BaseUpdater(get_settings().runtime_root.resolve() / "base-releases", key, WORKER_VERSION)
        raise SystemExit(0 if apply_handoff(updater, sys.argv[2]) else 1)
    except Exception:
        raise SystemExit(2) from None

from app.main import main
from app.skills.runner import main as skill_runner_main
from app.status_ui import main as status_ui_main


if len(sys.argv) > 1 and sys.argv[1] == "--skill-runner":
    raise SystemExit(skill_runner_main(sys.argv[2:]))
if len(sys.argv) > 1 and sys.argv[1] == "--worker-core":
    from app.process_control import redirect_to_active_core
    if redirect_to_active_core():
        raise SystemExit(0)
    raise SystemExit(main())
if len(sys.argv) > 1 and sys.argv[1] == "--status-ui":
    raise SystemExit(status_ui_main())
raise SystemExit(status_ui_main())
