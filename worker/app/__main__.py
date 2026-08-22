import sys

from app.main import main
from app.skills.runner import main as skill_runner_main
from app.status_ui import main as status_ui_main


if len(sys.argv) > 1 and sys.argv[1] == "--skill-runner":
    raise SystemExit(skill_runner_main(sys.argv[2:]))
if len(sys.argv) > 1 and sys.argv[1] == "--status-ui":
    raise SystemExit(status_ui_main())
raise SystemExit(main())
