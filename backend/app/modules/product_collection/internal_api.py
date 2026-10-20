"""Service-authenticated gateway registration and phone package ingest APIs."""

from __future__ import annotations

import hmac
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.core.exceptions import COMMON_ERROR_RESPONSES, ErrorResponse
from app.modules.product_collection.contracts import (
    GatewayAttemptRegistrationV1,
    GatewayAttemptRegistrationResponseV1,
    GatewayCredentialRefreshV1,
    UploadAcceptedV1,
)
from app.modules.product_collection.exceptions import (
    ProductCollectionConfigurationError,
    ProductCollectionPayloadTooLargeError,
    ProductCollectionServiceAuthenticationError,
)
from app.modules.product_collection.ingest_service import ProductCollectionIngestService
from app.modules.product_collection.payload import MAX_COMPLETE_PACKAGE_BYTES


router = APIRouter(
    prefix="/internal/mobile-collection/v1",
    tags=["product-collection-internal"],
    responses={
        **COMMON_ERROR_RESPONSES,
        401: {"model": ErrorResponse, "description": "服务或批次凭据无效"},
        409: {"model": ErrorResponse, "description": "任务批次或内容冲突"},
        413: {"model": ErrorResponse, "description": "完整包超过大小限制"},
    },
)
ingest_router = APIRouter(
    prefix="/api/v1/mobile-collection",
    tags=["product-collection-ingest"],
    responses=router.responses,
)
gateway_bearer = HTTPBearer(auto_error=False, scheme_name="ProductCollectionGateway")
ingest_bearer = HTTPBearer(auto_error=False, scheme_name="ProductCollectionIngest")


def get_ingest_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> ProductCollectionIngestService:
    return ProductCollectionIngestService(session)


def require_gateway_service(
    authorization: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(gateway_bearer),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    configured = settings.product_collection_service_token
    if configured is None:
        raise ProductCollectionConfigurationError()
    if (
        authorization is None
        or authorization.scheme.lower() != "bearer"
        or not hmac.compare_digest(
            authorization.credentials,
            configured.get_secret_value(),
        )
    ):
        raise ProductCollectionServiceAuthenticationError()


def require_ingest_credential(
    authorization: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(ingest_bearer),
    ],
) -> str:
    if authorization is None or authorization.scheme.lower() != "bearer":
        raise ProductCollectionServiceAuthenticationError()
    return authorization.credentials


@router.post(
    "/attempts/register",
    response_model=GatewayAttemptRegistrationResponseV1,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_gateway_service)],
)
def register_product_collection_attempt(
    registration: GatewayAttemptRegistrationV1,
    service: Annotated[ProductCollectionIngestService, Depends(get_ingest_service)],
    settings: Annotated[Settings, Depends(get_settings)],
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
) -> GatewayAttemptRegistrationResponseV1:
    secret = settings.product_collection_ingest_hmac_key
    public_base_url = settings.product_collection_public_base_url
    if secret is None or public_base_url is None:
        raise ProductCollectionConfigurationError()
    expected_key = (
        f"{registration.gateway_id}:{registration.gateway_job_id}:"
        f"{registration.capture_batch_id}"
    )
    if not hmac.compare_digest(idempotency_key, expected_key):
        from app.modules.product_collection.exceptions import (
            ProductCollectionBatchConflictError,
        )

        raise ProductCollectionBatchConflictError()
    control = service.register_attempt(
        registration,
        secret=secret.get_secret_value().encode("utf-8"),
        key_id=settings.product_collection_ingest_key_id,
        public_base_url=public_base_url,
        token_ttl_seconds=settings.product_collection_ingest_token_ttl_seconds,
        accept_grace_seconds=settings.product_collection_accept_grace_seconds,
    )
    return GatewayAttemptRegistrationResponseV1(controlIngest=control)


@router.post(
    "/attempts/{attempt_id}/credentials/refresh",
    response_model=GatewayAttemptRegistrationResponseV1,
    dependencies=[Depends(require_gateway_service)],
)
def refresh_product_collection_credential(
    attempt_id: UUID,
    command: GatewayCredentialRefreshV1,
    service: Annotated[ProductCollectionIngestService, Depends(get_ingest_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GatewayAttemptRegistrationResponseV1:
    secret = settings.product_collection_ingest_hmac_key
    public_base_url = settings.product_collection_public_base_url
    if secret is None or public_base_url is None:
        raise ProductCollectionConfigurationError()
    control = service.refresh_credential(
        attempt_id=attempt_id,
        command=command,
        secret=secret.get_secret_value().encode("utf-8"),
        public_base_url=public_base_url,
        token_ttl_seconds=settings.product_collection_ingest_token_ttl_seconds,
    )
    return GatewayAttemptRegistrationResponseV1(controlIngest=control)


@ingest_router.post(
    "/ingest/{attempt_id}",
    response_model=UploadAcceptedV1,
    status_code=status.HTTP_202_ACCEPTED,
)
async def accept_product_collection_complete_package(
    attempt_id: UUID,
    request: Request,
    credential: Annotated[str, Depends(require_ingest_credential)],
    service: Annotated[ProductCollectionIngestService, Depends(get_ingest_service)],
) -> UploadAcceptedV1:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_COMPLETE_PACKAGE_BYTES:
            raise ProductCollectionPayloadTooLargeError()
    return service.accept_complete_package(
        attempt_id=attempt_id,
        credential=credential,
        raw_body=bytes(body),
    )
