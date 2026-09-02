import argparse
import getpass
import sys
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_database_engine
from app.core.exceptions import AppError
from app.modules.access.service import AccessManagementService
from app.modules.human_auth.passwords import PasswordPolicyError, PasswordService
from app.modules.human_auth.service import HumanAuthService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理内部人员登录凭据")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap = subparsers.add_parser(
        "bootstrap",
        help="仅在users为空时创建第一个User并加入默认团队",
    )
    bootstrap.add_argument("--display-name", required=True)
    bootstrap.add_argument("--login-name", required=True)

    credentials = subparsers.add_parser(
        "set-credentials",
        help="为指定Existing User设置或重置登录凭据",
    )
    credentials.add_argument("user_id", type=UUID)
    credentials.add_argument("--login-name", required=True)

    grant_access_administrator = subparsers.add_parser(
        "grant-access-administrator",
        help="为一条启用成员关系授予用户与权限管理员身份",
    )
    grant_access_administrator.add_argument("membership_id", type=UUID)
    return parser


def _read_confirmed_password() -> str:
    password = getpass.getpass("新密码: ")
    confirmation = getpass.getpass("再次输入新密码: ")
    if password != confirmation:
        raise ValueError("两次输入的密码不一致")
    return password


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        with Session(get_database_engine()) as session:
            if args.command == "grant-access-administrator":
                AccessManagementService(
                    session,
                    PasswordService(),
                ).grant_access_administrator(args.membership_id)
                print(
                    "权限管理员已授予: "
                    f"membership_id={args.membership_id}",
                )
                return 0

            password = _read_confirmed_password()
            service = HumanAuthService(
                session,
                get_settings(),
                PasswordService(),
            )
            if args.command == "bootstrap":
                user = service.bootstrap_first_user(
                    display_name=args.display_name,
                    login_name=args.login_name,
                    password=password,
                )
                print(f"首次人员账号已创建: user_id={user.user_id}")
                return 0

            user = service.set_credentials(
                user_id=args.user_id,
                login_name=args.login_name,
                password=password,
            )
            print(f"人员登录凭据已更新且旧会话已撤销: user_id={user.user_id}")
            return 0
    except (AppError, PasswordPolicyError, ValueError) as error:
        message = error.message if isinstance(error, AppError) else str(error)
        print(f"操作失败: {message}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
