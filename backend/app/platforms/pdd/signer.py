from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from pydantic import SecretStr


ANTI_CONTENT_PATH = Path(__file__).with_name("vendor") / "anti_content.js"
CHILD_TIMEOUT_SECONDS = 15


class PddAntiContentSignerError(RuntimeError):
    """Safe failure boundary for the local PDD anti-content child process."""


class PddAntiContentSigner:
    """Generate one PDD anti-content value in one isolated Node process."""

    def __init__(
        self,
        *,
        signer_path: Path = ANTI_CONTENT_PATH,
        node_path: str | None = None,
    ) -> None:
        self.signer_path = signer_path
        self.node_path = node_path

    def generate(self) -> SecretStr:
        if not self.signer_path.is_file():
            raise PddAntiContentSignerError()
        node = self.node_path or self._resolve_node()
        if node is None:
            raise PddAntiContentSignerError()
        try:
            completed = subprocess.run(
                [node, "-e", _NODE_SCRIPT, str(self.signer_path)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=CHILD_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise PddAntiContentSignerError() from error
        if completed.returncode != 0:
            raise PddAntiContentSignerError()
        values = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        if not values:
            raise PddAntiContentSignerError()
        return SecretStr(values[-1])

    @staticmethod
    def _resolve_node() -> str | None:
        return shutil.which("node")


_NODE_SCRIPT = """
var fs = require('fs');
var code = fs.readFileSync(process.argv[1], 'utf8');
eval(code);
console.log(antigain());
"""
