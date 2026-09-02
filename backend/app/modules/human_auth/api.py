from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.config import Settings, get_settings
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import HumanPrincipal
from app.modules.human_auth.dependencies import get_human_auth_service
from app.modules.human_auth.schemas import CurrentHumanUserRead, HumanLoginRequest
from app.modules.human_auth.service import HumanAuthService


HUMAN_AUTH_ERROR_RESPONSES = cast(
    dict[int | str, dict[str, Any]],
    COMMON_ERROR_RESPONSES.copy(),
)
HUMAN_AUTH_ERROR_RESPONSES.update(
    {
        401: {"model": ErrorResponse, "description": "人员登录或会话无效"},
        403: {"model": ErrorResponse, "description": "人员账号已停用"},
    },
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["human-auth"],
    responses=HUMAN_AUTH_ERROR_RESPONSES,
)


def _set_session_cookie(
    response: Response,
    *,
    raw_token: str,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.human_session_cookie_name,
        value=raw_token,
        max_age=settings.human_session_ttl_seconds,
        path=settings.human_session_cookie_path,
        secure=settings.human_session_cookie_secure,
        httponly=True,
        samesite=settings.human_session_cookie_samesite,
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.human_session_cookie_name,
        path=settings.human_session_cookie_path,
        secure=settings.human_session_cookie_secure,
        httponly=True,
        samesite=settings.human_session_cookie_samesite,
    )


@router.post("/login", response_model=CurrentHumanUserRead)
def login(
    command: HumanLoginRequest,
    response: Response,
    service: Annotated[HumanAuthService, Depends(get_human_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CurrentHumanUserRead:
    result = service.login(command)
    _set_session_cookie(
        response,
        raw_token=result.raw_session_token,
        settings=settings,
    )
    response.headers["Cache-Control"] = "no-store"
    return CurrentHumanUserRead.model_validate(result.principal)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    service: Annotated[HumanAuthService, Depends(get_human_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    service.logout(request.cookies.get(settings.human_session_cookie_name))
    _clear_session_cookie(response, settings)
    response.headers["Cache-Control"] = "no-store"


@router.get("/me", response_model=CurrentHumanUserRead)
def get_current_human_user(
    response: Response,
    principal: Annotated[HumanPrincipal, Depends(get_human_principal)],
) -> CurrentHumanUserRead:
    response.headers["Cache-Control"] = "no-store"
    return CurrentHumanUserRead.model_validate(principal)
