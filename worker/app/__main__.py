import sys

from app.main import main
from app.skills.runner import main as skill_runner_main


if len(sys.argv) > 1 and sys.argv[1] == "--skill-runner":
    raise SystemExit(skill_runner_main(sys.argv[2:]))
raise SystemExit(main())
