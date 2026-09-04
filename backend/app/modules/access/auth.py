from typing import Annotated

from fastapi import Depends, Request

from app.core.logging.request import set_request_user_id
from app.modules.access.contracts import HumanPrincipal
from app.modules.human_auth.dependencies import get_human_auth_service
from app.modules.human_auth.service import HumanAuthService


def get_human_principal(
    request: Request,
    service: Annotated[HumanAuthService, Depends(get_human_auth_service)],
) -> HumanPrincipal:
    """从固定HttpOnly Cookie解析人员身份，不接受可伪造身份Header。"""

    principal = service.resolve_principal(
        request.cookies.get(service.settings.human_session_cookie_name),
    )
    set_request_user_id(request, principal.user_id)
    return principal
