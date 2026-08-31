from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
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
