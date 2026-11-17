"""Distribute offline-signed Worker base releases to authenticated devices."""
from pathlib import Path
import base64
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from app.modules.workers.auth import get_worker_principal
from app.modules.workers.capability_package_api import SignedManifestResponse, _read_artifact
from app.modules.workers.service import WorkerPrincipal


MAX_BASE_ARCHIVE_BYTES = 256 * 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def build_base_update_router(package_directory: Path | None) -> APIRouter:
    root = package_directory / "worker-base" if package_directory is not None else None
    router = APIRouter(prefix="/api/v1/worker/base-releases", tags=["worker"])

    @router.get("/manifest", response_model=SignedManifestResponse)
    def manifest(response: Response, _principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)]):
        data = _read_artifact(root, "manifest.json", 64 * 1024)
        signature = _read_artifact(root, "manifest.sig", 64)
        if len(signature) != 64:
            raise HTTPException(status_code=404, detail="Worker release unavailable")
        response.headers["Cache-Control"] = "no-store"
        return SignedManifestResponse(manifest=base64.b64encode(data).decode("ascii"),
                                      signature=base64.b64encode(signature).decode("ascii"))

    @router.get("/blobs/{digest}")
    def package(digest: str, _principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)]):
        if root is None or _DIGEST.fullmatch(digest) is None:
            raise HTTPException(status_code=404, detail="Worker release unavailable")
        try:
            directory = root.resolve(strict=True)
            packages = directory / "packages"
            path = packages / f"{digest}.zip"
            if root.is_symlink() or packages.is_symlink() or path.is_symlink():
                raise ValueError
            resolved = path.resolve(strict=True)
            resolved.relative_to(directory)
            if not resolved.is_file() or not 0 < resolved.stat().st_size <= MAX_BASE_ARCHIVE_BYTES:
                raise ValueError
        except (OSError, ValueError):
            raise HTTPException(status_code=404, detail="Worker release unavailable") from None
        return FileResponse(resolved, media_type="application/zip", headers={"Cache-Control": "no-store"})

    return router
