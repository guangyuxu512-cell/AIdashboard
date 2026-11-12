import sys

if len(sys.argv) == 3 and sys.argv[1] == "--check-version":
    from app.version import WORKER_VERSION
    raise SystemExit(0 if sys.argv[2] == WORKER_VERSION else 1)

if len(sys.argv) > 1 and sys.argv[1] == "--check-capability-trust":
    from app.release_trust import packaged_capability_public_key
    raise SystemExit(0 if packaged_capability_public_key() is not None else 2)

from app.main import main
from app.skills.runner import main as skill_runner_main
from app.status_ui import main as status_ui_main


if len(sys.argv) > 1 and sys.argv[1] == "--skill-runner":
    raise SystemExit(skill_runner_main(sys.argv[2:]))
if len(sys.argv) > 1 and sys.argv[1] == "--worker-core":
    raise SystemExit(main())
if len(sys.argv) > 1 and sys.argv[1] == "--status-ui":
    raise SystemExit(status_ui_main())
raise SystemExit(status_ui_main())
