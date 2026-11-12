"""Authenticated application and Worker entry points for category precheck."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_database_session
from app.integrations.douyin_signer.client import DouyinSignerClient
from app.modules.sessions.application_api import bearer
from app.modules.sessions.application_auth import ApplicationAuthenticationError, ApplicationAuthenticator, ApplicationPrincipal, ApplicationTransportError
from app.modules.workers.auth import get_worker_principal
from app.modules.workers.precheck_contract import PrecheckDeliveryAcknowledgement, PrecheckSignInput, PrecheckSubmission, PrecheckTerminal, RpaInventoryReport
from app.modules.workers.precheck_service import PrecheckInvalidResult, PrecheckUnavailable, WorkerPrecheckService, accept_precheck_terminal, acknowledge_product_delivery, product_delivery_context, save_rpa_inventory, sign_current_precheck
from app.modules.workers.service import WorkerPrincipal


application_router = APIRouter(prefix="/internal/applications/v1", tags=["application-worker-precheck"])
worker_router = APIRouter(prefix="/api/v1/worker", tags=["worker-precheck"])


def _enabled(settings: Annotated[Settings, Depends(get_settings)]) -> None:
    if not settings.application_worker_precheck_enabled:
        raise PrecheckUnavailable()


def _precheck_authenticator(settings: Annotated[Settings, Depends(get_settings)]) -> ApplicationAuthenticator:
    return ApplicationAuthenticator(enabled=settings.application_worker_precheck_enabled,
        path=settings.application_worker_precheck_clients_file or settings.application_shop_session_clients_file)


def require_precheck_application(
    request: Request,
    auth: Annotated[ApplicationAuthenticator, Depends(_precheck_authenticator)],
    authorization: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    client_id: Annotated[str | None, Header(alias="X-Application-ID")] = None,
) -> ApplicationPrincipal:
    if request.url.scheme != "https":
        raise ApplicationTransportError()
    if authorization is None or authorization.scheme.lower() != "bearer" or client_id is None:
        raise ApplicationAuthenticationError()
    return auth.authenticate(client_id, authorization.credentials)


def _service(session: Annotated[Session, Depends(get_database_session)],
             auth: Annotated[ApplicationAuthenticator, Depends(_precheck_authenticator)]) -> WorkerPrecheckService:
    return WorkerPrecheckService(session, auth)


@application_router.post("/worker-prechecks", status_code=status.HTTP_202_ACCEPTED,
                         dependencies=[Depends(_enabled)])
def submit_precheck(data: PrecheckSubmission, response: Response,
                    principal: Annotated[ApplicationPrincipal, Depends(require_precheck_application)],
                    service: Annotated[WorkerPrecheckService, Depends(_service)]) -> dict:
    task = service.submit(principal, data)
    response.headers["Cache-Control"] = "no-store"
    return {"task_id": str(task.task_id), "status": task.status}


@application_router.get("/worker-prechecks/{task_id}", dependencies=[Depends(_enabled)])
def get_precheck(task_id: UUID, response: Response,
                 principal: Annotated[ApplicationPrincipal, Depends(require_precheck_application)],
                 service: Annotated[WorkerPrecheckService, Depends(_service)]) -> dict:
    task = service.get(principal, task_id)
    response.headers["Cache-Control"] = "no-store"
    return {"task_id": str(task.task_id), "status": task.status, "result": task.result_json,
            "error_code": task.error_code, "error_message": task.error_message}


@worker_router.put("/rpa-shop-inventory", status_code=status.HTTP_204_NO_CONTENT,
                   dependencies=[Depends(_enabled)])
def put_rpa_inventory(data: RpaInventoryReport,
                      principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
                      session: Annotated[Session, Depends(get_database_session)]) -> Response:
    save_rpa_inventory(session, principal.device_id, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@worker_router.post("/tasks/{task_id}/precheck-result", dependencies=[Depends(_enabled)])
def finish_precheck(task_id: UUID, data: PrecheckTerminal,
                    principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
                    session: Annotated[Session, Depends(get_database_session)]) -> dict:
    task = accept_precheck_terminal(session, principal.device_id, task_id, data)
    return {"task_id": str(task.task_id), "status": task.status}


@worker_router.get("/tasks/{task_id}/precheck-delivery-context", dependencies=[Depends(_enabled)])
def get_delivery_context(task_id: UUID, response: Response,
                         principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
                         session: Annotated[Session, Depends(get_database_session)],
                         auth: Annotated[ApplicationAuthenticator, Depends(_precheck_authenticator)]) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return product_delivery_context(session, auth, principal.device_id, task_id)


@worker_router.post("/tasks/{task_id}/precheck-delivered", dependencies=[Depends(_enabled)])
def finish_product_delivery(task_id: UUID, data: PrecheckDeliveryAcknowledgement,
                            principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
                            session: Annotated[Session, Depends(get_database_session)]) -> dict:
    task = acknowledge_product_delivery(session, principal.device_id, task_id, data)
    return {"task_id": str(task.task_id), "status": task.status}


@worker_router.post("/tasks/{task_id}/precheck-sign", dependencies=[Depends(_enabled)])
async def sign_precheck(task_id: UUID, request: Request, response: Response,
                        principal: Annotated[WorkerPrincipal, Depends(get_worker_principal)],
                        session: Annotated[Session, Depends(get_database_session)],
                        auth: Annotated[ApplicationAuthenticator, Depends(_precheck_authenticator)],
                        settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, str]:
    # The payload is read manually so malformed Cookie input is never echoed
    # by generic request-validation errors. HTTPS is mandatory even for Worker.
    if request.url.scheme != "https":
        raise ApplicationTransportError()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 40 * 1024:
            raise PrecheckInvalidResult()
    try:
        data = PrecheckSignInput.model_validate_json(body)
    except (ValueError, ValidationError):
        raise PrecheckInvalidResult() from None
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return await run_in_threadpool(sign_current_precheck, session, auth, DouyinSignerClient(settings=settings),
                                   principal.device_id, task_id, data)
