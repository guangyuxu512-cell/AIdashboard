from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.modules.access.exceptions import HumanAuthenticationRequiredError
from app.modules.human_auth.passwords import PasswordService
from app.modules.human_auth.service import HumanAuthService


@lru_cache
def get_password_service() -> PasswordService:
    return PasswordService()


def get_human_auth_service(
    session: Annotated[Session, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    password_service: Annotated[PasswordService, Depends(get_password_service)],
) -> HumanAuthService:
    return HumanAuthService(session, settings, password_service)


def get_human_session_token(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> str:
    """Fail an anonymous request before opening a database session."""

    raw_session_token = request.cookies.get(settings.human_session_cookie_name)
    if not raw_session_token:
        raise HumanAuthenticationRequiredError()
    return raw_session_token


def get_authenticated_human_auth_service(
    _raw_session_token: Annotated[str, Depends(get_human_session_token)],
    session: Annotated[Session, Depends(get_database_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    password_service: Annotated[PasswordService, Depends(get_password_service)],
) -> HumanAuthService:
    """Construct the session-backed service only after cookie presence is known."""

    return HumanAuthService(session, settings, password_service)
