import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exceptions import install_exception_handlers
from app.core.health import router as health_router
from app.core.logging import RequestLoggingMiddleware
from app.modules.access.api import router as access_router
from app.modules.access.management_api import router as access_management_router
from app.modules.api_tokens.api import router as api_tokens_router
from app.modules.token_management.api import router as token_management_router
from app.modules.api_tokens.catalog import install_openapi_security
from app.modules.audit.api import router as audit_log_router
from app.modules.assets.api import router as assets_router
from app.modules.devices.api import router as devices_router
from app.modules.human_auth.api import router as human_auth_router
from app.modules.notifications.api import router as notifications_router
from app.modules.operating_dashboard.api import router as operating_dashboard_router
from app.modules.product_data.api import router as product_data_router
from app.modules.schedules.api import router as schedules_router
from app.modules.schedules.scheduler import trigger_due_schedules_forever
from app.modules.tasks.api import router as tasks_router
from app.modules.tasks.reconcile import reconcile_lost_tasks_forever
from app.modules.tasks.retention import purge_expired_task_events_forever
from app.modules.tasks.worker_api import router as worker_tasks_router
from app.modules.users.api import router as users_router
from app.modules.workers.api import router as workers_router
from app.modules.workers.capability_package_api import build_capability_package_router
from app.modules.workers.base_update_api import build_base_update_router
from app.modules.workers.precheck_api import application_router as application_worker_precheck_router
from app.modules.workers.precheck_api import worker_router as worker_precheck_router
from app.modules.workers.selection_delivery_api import router as worker_selection_delivery_router
from app.modules.workers.reconcile import reconcile_offline_devices_forever


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    del application
    settings = get_settings()
    reconcile_task = asyncio.create_task(reconcile_lost_tasks_forever())
    offline_reconcile_task = asyncio.create_task(reconcile_offline_devices_forever())
    retention_task = asyncio.create_task(purge_expired_task_events_forever())
    schedule_task = (
        asyncio.create_task(trigger_due_schedules_forever())
        if settings.worker_schedule_execution_enabled
        else None
    )
    try:
        yield
    finally:
        reconcile_task.cancel()
        offline_reconcile_task.cancel()
        retention_task.cancel()
        if schedule_task is not None:
            schedule_task.cancel()
        with suppress(asyncio.CancelledError):
            await reconcile_task
        with suppress(asyncio.CancelledError):
            await offline_reconcile_task
        with suppress(asyncio.CancelledError):
            await retention_task
        if schedule_task is not None:
            with suppress(asyncio.CancelledError):
                await schedule_task


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="Ecommerce AI Control Center Backend",
        lifespan=lifespan,
    )
    if settings.cors_allowed_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
            allow_headers=[
                "Accept",
                "Authorization",
                "Content-Type",
                "X-Device-ID",
                "X-Request-ID",
                "X-Team-ID",
            ],
            expose_headers=["X-Request-ID"],
        )
    application.add_middleware(RequestLoggingMiddleware)
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(human_auth_router)
    application.include_router(access_router)
    application.include_router(access_management_router)
    application.include_router(api_tokens_router)
    application.include_router(token_management_router)
    application.include_router(audit_log_router)
    application.include_router(assets_router)
    application.include_router(users_router)
    application.include_router(devices_router)
    application.include_router(notifications_router)
    application.include_router(operating_dashboard_router)
    application.include_router(product_data_router)
    application.include_router(application_worker_precheck_router)
    application.include_router(tasks_router)
    application.include_router(schedules_router)
    from app.modules.schedules.operations_api import router as operations_schedule_router
    application.include_router(operations_schedule_router)
    application.include_router(workers_router)
    application.include_router(build_capability_package_router(get_settings().worker_capability_package_dir))
    application.include_router(build_base_update_router(get_settings().worker_capability_package_dir))
    application.include_router(worker_precheck_router)
    application.include_router(worker_selection_delivery_router)
    application.include_router(worker_tasks_router)
    install_openapi_security(application, settings.human_session_cookie_name)
    return application


app = create_app()
