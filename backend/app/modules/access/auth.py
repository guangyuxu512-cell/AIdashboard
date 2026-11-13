from typing import Annotated

from fastapi import Depends, Request

from app.core.logging.request import set_request_user_id
from app.modules.access.contracts import HumanPrincipal
from app.modules.human_auth.dependencies import (
    get_authenticated_human_auth_service,
    get_human_session_token,
)
from app.modules.human_auth.service import HumanAuthService


def get_human_principal(
    request: Request,
    raw_session_token: Annotated[str, Depends(get_human_session_token)],
    service: Annotated[
        HumanAuthService,
        Depends(get_authenticated_human_auth_service),
    ],
) -> HumanPrincipal:
    """Authenticate the human cookie or a separately scoped management token."""

    if request.headers.get("Authorization") is not None:
        from app.modules.api_tokens.exceptions import ApiTokenPermissionDeniedError
        from app.modules.api_tokens.service import ApiTokenService

        principal = ApiTokenService(service.session).authenticate(raw_session_token)
        route = request.scope.get("route")
        permission = f"{request.method.upper()} {getattr(route, 'path', '')}"
        if permission not in principal.api_permissions:
            raise ApiTokenPermissionDeniedError()
    else:
        principal = service.resolve_principal(raw_session_token)
    set_request_user_id(request, principal.user_id)
    return principal
