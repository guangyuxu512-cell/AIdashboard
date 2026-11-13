from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_database_session
from app.core.logging.request import get_request_id
from app.modules.access.auth import get_human_principal
from app.modules.access.contracts import ActorContext, HumanPrincipal
from app.modules.access.dependencies import get_super_account
from app.modules.access.exceptions import AccessAdministrationForbiddenError
from app.modules.api_tokens.catalog import permissions_catalog
from app.modules.api_tokens.schemas import ApiTokenChange, ApiTokenEnabled, ApiTokenEventRead, ApiTokenIssued, ApiTokenRead, PermissionRead
from app.modules.api_tokens.service import ApiTokenService

router = APIRouter(prefix="/api/v1/api-tokens", tags=["api-tokens"])


def require_human_administrator(
    principal: Annotated[HumanPrincipal, Depends(get_human_principal)],
    actor: Annotated[ActorContext, Depends(get_super_account)],
) -> ActorContext:
    # Token issuance cannot be delegated accidentally by granting a business
    # endpoint; the operator uses the existing administrator login.
    if principal.api_token_id is not None:
        raise AccessAdministrationForbiddenError()
    return actor


def get_service(session: Annotated[Session, Depends(get_database_session)]) -> ApiTokenService:
    return ApiTokenService(session)


@router.get("/permissions", response_model=list[PermissionRead])
def list_permissions(request: Request, response: Response, _actor: Annotated[ActorContext, Depends(require_human_administrator)]) -> list[dict]:
    response.headers["Cache-Control"] = "no-store"
    return permissions_catalog(request.app)


@router.get("", response_model=list[ApiTokenRead])
def list_tokens(response: Response, _actor: Annotated[ActorContext, Depends(require_human_administrator)], service: Annotated[ApiTokenService, Depends(get_service)]) -> list:
    response.headers["Cache-Control"] = "no-store"
    return service.list()


@router.post("", response_model=ApiTokenIssued, status_code=status.HTTP_201_CREATED)
def create_token(command: ApiTokenChange, request: Request, response: Response, actor: Annotated[ActorContext, Depends(require_human_administrator)], service: Annotated[ApiTokenService, Depends(get_service)]) -> ApiTokenIssued:
    issued = service.issue(actor=actor, request_id=get_request_id(request), catalog=permissions_catalog(request.app), **command.model_dump())
    response.headers["Cache-Control"] = "no-store"
    return ApiTokenIssued(token=ApiTokenRead.model_validate(issued.record), value=issued.raw_token)


@router.put("/{token_id}", response_model=ApiTokenRead)
def update_token(token_id: UUID, command: ApiTokenChange, request: Request, response: Response, actor: Annotated[ActorContext, Depends(require_human_administrator)], service: Annotated[ApiTokenService, Depends(get_service)]) -> ApiTokenRead:
    record = service.update(token_id, actor=actor, request_id=get_request_id(request), catalog=permissions_catalog(request.app), **command.model_dump())
    response.headers["Cache-Control"] = "no-store"
    return ApiTokenRead.model_validate(record)


@router.get("/{token_id}/events", response_model=list[ApiTokenEventRead])
def list_token_events(token_id: UUID, response: Response, _actor: Annotated[ActorContext, Depends(require_human_administrator)], service: Annotated[ApiTokenService, Depends(get_service)]) -> list:
    response.headers["Cache-Control"] = "no-store"
    return service.list_events(token_id)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_token(token_id: UUID, request: Request, actor: Annotated[ActorContext, Depends(require_human_administrator)], service: Annotated[ApiTokenService, Depends(get_service)]) -> Response:
    service.revoke(token_id, actor=actor, request_id=get_request_id(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


@router.patch("/{token_id}/enabled", response_model=ApiTokenRead)
def set_token_enabled(token_id: UUID, command: ApiTokenEnabled, request: Request, response: Response, actor: Annotated[ActorContext, Depends(require_human_administrator)], service: Annotated[ApiTokenService, Depends(get_service)]) -> ApiTokenRead:
    record = service.set_enabled(token_id, actor=actor, request_id=get_request_id(request), enabled=command.enabled)
    response.headers["Cache-Control"] = "no-store"
    return ApiTokenRead.model_validate(record)
