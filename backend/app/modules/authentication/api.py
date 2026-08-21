from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.authentication.schemas import (
    CompleteManagementOnboardingCommand,
    ManagementOnboardingResult,
)
from app.modules.authentication.service import ManagementOnboardingService


router = APIRouter(
    prefix="/api/v1/shop-onboarding",
    tags=["shop-onboarding"],
    responses={
        **COMMON_ERROR_RESPONSES,
        409: {"model": ErrorResponse, "description": "平台店铺已经接入"},
    },
)


def get_management_onboarding_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> ManagementOnboardingService:
    return ManagementOnboardingService(session, cipher)


@router.post(
    "/complete",
    response_model=ManagementOnboardingResult,
    status_code=status.HTTP_201_CREATED,
)
def complete_management_onboarding(
    command: CompleteManagementOnboardingCommand,
    service: Annotated[
        ManagementOnboardingService,
        Depends(get_management_onboarding_service),
    ],
) -> ManagementOnboardingResult:
    return service.complete(command)
