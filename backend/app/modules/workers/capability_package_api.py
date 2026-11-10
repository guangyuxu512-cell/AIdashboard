"""Authenticated distribution of offline-signed Worker capability packages.

The server stores only already-signed release artifacts.  It does not hold a
signing key or accept commands, file paths, or unsigned package uploads.
"""

from __future__ import annotations

import base64
from pathlib import Path
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from app.modules.workers.auth import get_worker_principal
from app.modules.workers.service import WorkerPrincipal

MAX_MANIFEST_BYTES = 64 * 1024
MAX_PACKAGE_BYTES = 25 * 1024 * 1024
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


class SignedManifestResponse(BaseModel):
    manifest: str
    signature: str


def _read_artifact(root: Path | None, relative: str, limit: int) -> bytes:
    if root is None:
        raise HTTPException(status_code=503, detail="Capability packages are not configured")
    try:
        directory = root.resolve(strict=True)
        path = directory.joinpath(*relative.split("/"))
        # Do not let a published-artifact path escape its configured directory.
        if any(part.is_symlink() for part in (path, path.parent)):
            raise FileNotFoundError
        resolved = path.resolve(strict=True)
        resolved.relative_to(directory)
        with resolved.open("rb") as stream:
            value = stream.read(limit + 1)
        if len(value) > limit:
            raise ValueError
        return value
    except (OSError, ValueError):
        raise HTTPException(status_code=404, detail="Capability artifact unavailable") from None


def build_capability_package_router(package_directory: Path | None) -> APIRouter:
    """Build the router with a trusted server-local directory from settings."""
    router = APIRouter(prefix="/api/v1/worker/capability-packages", tags=["worker"])

    @router.get("/manifest", response_model=SignedManifestResponse)
    def manifest(
        response: Response,
        _principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    ) -> SignedManifestResponse:
        data = _read_artifact(package_directory, "manifest.json", MAX_MANIFEST_BYTES)
        signature = _read_artifact(package_directory, "manifest.sig", 64)
        if len(signature) != 64:
            raise HTTPException(status_code=404, detail="Capability artifact unavailable")
        response.headers["Cache-Control"] = "no-store"
        return SignedManifestResponse(
            manifest=base64.b64encode(data).decode("ascii"),
            signature=base64.b64encode(signature).decode("ascii"),
        )

    @router.get("/blobs/{digest}")
    def package(
        digest: str,
        _principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
    ) -> Response:
        if _DIGEST.fullmatch(digest) is None:
            raise HTTPException(status_code=404, detail="Capability artifact unavailable")
        data = _read_artifact(package_directory, f"packages/{digest}.zip", MAX_PACKAGE_BYTES)
        return Response(data, media_type="application/zip", headers={"Cache-Control": "no-store"})

    return router
