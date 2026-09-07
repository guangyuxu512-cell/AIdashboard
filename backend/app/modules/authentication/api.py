from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import require_module_access
from app.modules.access.module_access import ModuleCode
from app.modules.authentication.schemas import (
    CompleteManagementOnboardingCommand,
    ManagementOnboardingResult,
    PddManagementLoginIdentityResult,
    VerifyPddManagementLoginCommand,
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


get_shop_authorized_actor = require_module_access(ModuleCode.SHOP)


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
    _actor: Annotated[ActorContext, Depends(get_shop_authorized_actor)],
    service: Annotated[
        ManagementOnboardingService,
        Depends(get_management_onboarding_service),
    ],
) -> ManagementOnboardingResult:
    return service.complete(command)


@router.post(
    "/pdd/identity",
    response_model=PddManagementLoginIdentityResult,
)
def verify_pdd_management_login_identity(
    command: VerifyPddManagementLoginCommand,
    _actor: Annotated[ActorContext, Depends(get_shop_authorized_actor)],
    service: Annotated[
        ManagementOnboardingService,
        Depends(get_management_onboarding_service),
    ],
) -> PddManagementLoginIdentityResult:
    return service.verify_pdd_identity(command)
