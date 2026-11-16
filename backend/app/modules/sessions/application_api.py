from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.core.logging.request import get_request_id
from app.modules.sessions.application_auth import (
    ApplicationAuthenticationError,
    ApplicationAuthenticator,
    ApplicationPrincipal,
    ApplicationTransportError,
)
from app.modules.sessions.application_contract import ApplicationSessionRead, ApplicationShopRead
from app.modules.sessions.application_service import ApplicationSessionService


router = APIRouter(prefix="/internal/applications/v1", tags=["application-sessions"])
bearer = HTTPBearer(auto_error=False, scheme_name="ApplicationShopSession")


def authenticator(settings: Annotated[Settings, Depends(get_settings)]) -> ApplicationAuthenticator:
    return ApplicationAuthenticator(
        enabled=settings.application_shop_session_enabled,
        path=settings.application_shop_session_clients_file,
    )


def require_application(
    request: Request,
    authorizer: Annotated[ApplicationAuthenticator, Depends(authenticator)],
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    client_id: Annotated[str | None, Header(alias="X-Application-ID")] = None,
) -> ApplicationPrincipal:
    # Do not trust a client-supplied X-Forwarded-Proto.  The ASGI server must
    # receive HTTPS directly or trust only the explicitly configured TLS proxy.
    if request.url.scheme != "https":
        raise ApplicationTransportError()
    if authorization is None or authorization.scheme.lower() != "bearer" or client_id is None:
        raise ApplicationAuthenticationError()
    return authorizer.authenticate(client_id, authorization.credentials)


def get_application_session_service(
    session: Annotated[Session, Depends(get_database_session)],
    authorizer: Annotated[ApplicationAuthenticator, Depends(authenticator)],
) -> ApplicationSessionService:
    return ApplicationSessionService(session, authorizer)


def _safe_request_id(request: Request) -> str:
    value = get_request_id(request)
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        return str(uuid4())


@router.get("/shops", response_model=list[ApplicationShopRead])
def list_application_shops(
    response: Response,
    principal: Annotated[ApplicationPrincipal, Depends(require_application)],
    service: Annotated[ApplicationSessionService, Depends(get_application_session_service)],
) -> list[ApplicationShopRead]:
    response.headers["Cache-Control"] = "no-store"
    return service.list_shops(principal)


@router.get("/shops/{shop_id}/session", response_model=ApplicationSessionRead)
def read_application_shop_session(
    shop_id: UUID,
    request: Request,
    response: Response,
    principal: Annotated[ApplicationPrincipal, Depends(require_application)],
    service: Annotated[ApplicationSessionService, Depends(get_application_session_service)],
) -> ApplicationSessionRead:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return service.read_session(principal, shop_id=shop_id, request_id=_safe_request_id(request))
