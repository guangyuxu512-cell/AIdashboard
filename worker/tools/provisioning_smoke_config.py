"""Configure an isolated package-smoke data root through the production services.

This development-only helper reads its JSON payload from stdin so a Worker Token is
never placed in a command line or plaintext intermediary file. Ordinary users use
the packaged Tkinter GUI instead.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.local_config import WorkerConfigService
from app.providers.yingdao import WindowsYingdaoRuntimeLocator
from app.provisioning import WorkerProvisioningClient


def main() -> int:
    payload = json.load(sys.stdin)
    server_url = str(payload["server_url"])
    token = str(payload["device_token"])
    result = WorkerProvisioningClient().test(server_url, token)
    if not result.ok or result.identity is None:
        raise RuntimeError(f"Provisioning test failed: {result.code}")

    configured_root = payload.get("yingdao_install_root")
    executable = (
        WindowsYingdaoRuntimeLocator(Path(str(configured_root))).find_supported_executable()
        if configured_root
        else None
    )
    if configured_root and executable is None:
        raise RuntimeError("ShadowBot 6.3.6 was not found")

    WorkerConfigService().save(
        server_url=server_url,
        device_id=result.identity.device_id,
        device_token=token,
        device_display_name=result.identity.device_display_name,
        yingdao_install_root=executable.parent if executable is not None else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
