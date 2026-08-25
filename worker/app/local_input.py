from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import tempfile
from typing import Any, Protocol

from app.contracts import AccountPayload
from app.local_config import LocalInputPaths, write_json_atomic


class LocalInputPreparationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class LocalInputPreparer(Protocol):
    def prepare(
        self,
        *,
        params: Mapping[str, Any],
        accounts: Sequence[AccountPayload],
    ) -> None: ...


class LocalInputBridge:
    """Prepare the fixed local input consumed by external Yingdao applications."""

    def __init__(self, paths: LocalInputPaths) -> None:
        self.paths = LocalInputPaths(
            params_json_path=paths.params_json_path.resolve(),
            account_json_path=paths.account_json_path.resolve(),
            images_dir=paths.images_dir.resolve(),
        )

    def prepare(
        self,
        *,
        params: Mapping[str, Any],
        accounts: Sequence[AccountPayload],
    ) -> None:
        try:
            write_json_atomic(self.paths.params_json_path, dict(params))
        except (OSError, TypeError, ValueError) as error:
            raise LocalInputPreparationError(
                "LOCAL_PARAMS_FILE_PREPARATION_FAILED",
                "本地参数文件准备失败",
            ) from error
        try:
            write_json_atomic(
                self.paths.account_json_path,
                {
                    "店铺列表": [
                        {
                            "店铺ID": str(account.shop_id),
                            "平台编码": account.platform_code,
                            "登录账号": account.login_identifier,
                            "登录密码": account.secret,
                            "首选验证方式": account.preferred_verification_channel,
                        }
                        for account in accounts
                    ],
                },
            )
        except (OSError, TypeError, ValueError) as error:
            raise LocalInputPreparationError(
                "LOCAL_ACCOUNT_FILE_PREPARATION_FAILED",
                "账号文件准备失败",
            ) from error
        ensure_images_directory(self.paths.images_dir)


def ensure_images_directory(images_dir: Path) -> None:
    try:
        images_dir.mkdir(parents=True, exist_ok=True)
        if not images_dir.is_dir() or images_dir.parent == images_dir:
            raise OSError("images path is not a managed directory")
        descriptor, probe_name = tempfile.mkstemp(
            prefix=".ecommerce-worker-write-",
            dir=images_dir,
        )
        os.close(descriptor)
        Path(probe_name).unlink(missing_ok=True)
    except (OSError, TypeError) as error:
        raise LocalInputPreparationError(
            "LOCAL_IMAGES_DIRECTORY_UNAVAILABLE",
            "图片目录不可用",
        ) from error
