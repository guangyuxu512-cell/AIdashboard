import argparse
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.database import get_database_engine
from app.modules.workers.service import WorkerService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage per-device Worker tokens")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("issue", "rotate", "disable"):
        child = subparsers.add_parser(command)
        child.add_argument("device_id", type=UUID)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with Session(get_database_engine()) as session:
        service = WorkerService(session)
        if args.command == "disable":
            service.disable_token(args.device_id)
            print(f"Worker token disabled for device {args.device_id}")
            return 0
        token = (
            service.rotate_token(args.device_id)
            if args.command == "rotate"
            else service.issue_token(args.device_id)
        )
        print(f"WORKER_DEVICE_ID={args.device_id}")
        print(f"WORKER_DEVICE_TOKEN={token}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
