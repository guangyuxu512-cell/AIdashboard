import os
from pathlib import Path
import tempfile


class LocalInputPreparationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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
