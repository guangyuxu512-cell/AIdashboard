from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_LENGTH = 256


class PasswordPolicyError(ValueError):
    pass


class PasswordService:
    """使用 pwdlib 推荐的 Argon2 参数处理人员密码。"""

    def __init__(self, password_hash: PasswordHash | None = None) -> None:
        self.password_hash = password_hash or PasswordHash.recommended()
        self._dummy_hash = self.password_hash.hash(
            "human-auth-dummy-verification-value",
        )

    def hash_password(self, password: str) -> str:
        self.validate_new_password(password)
        return self.password_hash.hash(password)

    def verify_and_update(
        self,
        password: str,
        password_hash: str,
    ) -> tuple[bool, str | None]:
        try:
            return self.password_hash.verify_and_update(password, password_hash)
        except UnknownHashError:
            return False, None

    def burn_unknown_login_time(self, password: str) -> None:
        self.verify_and_update(password, self._dummy_hash)

    @staticmethod
    def validate_new_password(password: str) -> None:
        if len(password) < PASSWORD_MIN_LENGTH:
            raise PasswordPolicyError(
                f"密码至少需要{PASSWORD_MIN_LENGTH}个字符",
            )
        if len(password) > PASSWORD_MAX_LENGTH:
            raise PasswordPolicyError(
                f"密码不能超过{PASSWORD_MAX_LENGTH}个字符",
            )
