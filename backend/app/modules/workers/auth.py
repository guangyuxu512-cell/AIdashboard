from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.modules.workers.exceptions import WorkerAuthenticationError
from app.modules.workers.service import WorkerPrincipal, WorkerService


worker_bearer = HTTPBearer(auto_error=False)


def get_worker_principal(
    session: Annotated[Session, Depends(get_database_session)],
    authorization: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(worker_bearer),
    ],
    device_id: Annotated[str | None, Header(alias="X-Device-ID")] = None,
) -> WorkerPrincipal:
    if (
        device_id is None
        or authorization is None
        or authorization.scheme.lower() != "bearer"
    ):
        raise WorkerAuthenticationError()
    try:
        parsed_device_id = UUID(device_id)
    except ValueError as error:
        raise WorkerAuthenticationError() from error
    return WorkerService(session).authenticate(
        parsed_device_id,
        authorization.credentials,
    )


def get_worker_provisioning_principal(
    session: Annotated[Session, Depends(get_database_session)],
    authorization: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(worker_bearer),
    ],
) -> WorkerPrincipal:
    if authorization is None or authorization.scheme.lower() != "bearer":
        raise WorkerAuthenticationError()
    return WorkerService(session).authenticate_token(authorization.credentials)
