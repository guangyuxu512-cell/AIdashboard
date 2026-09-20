from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.core.security import SecretCipher, get_secret_cipher
from app.modules.access.contracts import ActorContext
from app.modules.access.dependencies import get_super_account
from app.modules.credentials.schemas import (
    CredentialCreate,
    CredentialStatusRead,
    CredentialUpdate,
)
from app.modules.credentials.service import CredentialService


# Existing dependency override consumers retain this import path.  It is an
# exact alias of the super-account guard, not a Shop-module permission path.
get_shop_authorized_actor = get_super_account


router = APIRouter(
    prefix="/api/v1",
    tags=["credentials"],
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": ErrorResponse, "description": "店铺或账号凭证不存在"},
        409: {"model": ErrorResponse, "description": "账号凭证关系冲突"},
    },
)


def get_credential_service(
    session: Annotated[Session, Depends(get_database_session)],
    cipher: Annotated[SecretCipher, Depends(get_secret_cipher)],
) -> CredentialService:
    return CredentialService(session, cipher)


@router.get(
    "/shops/{shop_id}/credential",
    response_model=CredentialStatusRead,
)
def get_shop_credential_status(
    shop_id: UUID,
    _actor: Annotated[ActorContext, Depends(get_shop_authorized_actor)],
    service: Annotated[CredentialService, Depends(get_credential_service)],
) -> CredentialStatusRead:
    return service.get_status_for_shop(shop_id)


@router.post(
    "/credentials",
    response_model=CredentialStatusRead,
    status_code=status.HTTP_201_CREATED,
)
def create_credential(
    data: CredentialCreate,
    _actor: Annotated[ActorContext, Depends(get_shop_authorized_actor)],
    service: Annotated[CredentialService, Depends(get_credential_service)],
) -> CredentialStatusRead:
    return service.create(data)


@router.patch(
    "/credentials/{credential_id}",
    response_model=CredentialStatusRead,
)
def update_credential(
    credential_id: UUID,
    data: CredentialUpdate,
    _actor: Annotated[ActorContext, Depends(get_shop_authorized_actor)],
    service: Annotated[CredentialService, Depends(get_credential_service)],
) -> CredentialStatusRead:
    return service.update(credential_id, data)


@router.post(
    "/credentials/{credential_id}/disable",
    response_model=CredentialStatusRead,
)
def disable_credential(
    credential_id: UUID,
    _actor: Annotated[ActorContext, Depends(get_shop_authorized_actor)],
    service: Annotated[CredentialService, Depends(get_credential_service)],
) -> CredentialStatusRead:
    return service.disable(credential_id)
