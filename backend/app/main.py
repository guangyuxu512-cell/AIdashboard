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
from app.modules.audit.api import router as audit_log_router
from app.modules.ai_workbench.api import router as ai_workbench_router
from app.modules.ai_workbench.generation_executor import (
    execute_generation_items_forever,
)
from app.modules.ai_workbench.model_catalog_api import (
    admin_router as ai_model_admin_router,
    catalog_router as ai_model_catalog_router,
)
from app.modules.authentication.api import router as authentication_router
from app.modules.assets.api import router as assets_router
from app.modules.automation_apps.api import router as automation_apps_router
from app.modules.automation_apps.presets_api import (
    management_router as automation_parameter_preset_management_router,
    router as automation_parameter_presets_router,
)
from app.modules.credentials.api import router as credentials_router
from app.modules.devices.api import router as devices_router
from app.modules.human_auth.api import router as human_auth_router
from app.modules.notifications.api import router as notifications_router
from app.modules.schedules.api import router as schedules_router
from app.modules.schedules.scheduler import trigger_due_schedules_forever
from app.modules.sessions.api import router as sessions_router
from app.modules.shops.api import router as shops_router
from app.modules.tasks.api import router as tasks_router
from app.modules.tasks.reconcile import reconcile_lost_tasks_forever
from app.modules.tasks.retention import purge_expired_task_events_forever
from app.modules.tasks.worker_api import router as worker_tasks_router
from app.modules.users.api import router as users_router
from app.modules.workers.api import router as workers_router
from app.modules.workers.reconcile import reconcile_offline_devices_forever


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    del application
    settings = get_settings()
    reconcile_task = asyncio.create_task(reconcile_lost_tasks_forever())
    offline_reconcile_task = asyncio.create_task(reconcile_offline_devices_forever())
    retention_task = asyncio.create_task(purge_expired_task_events_forever())
    schedule_task = asyncio.create_task(trigger_due_schedules_forever())
    generation_task = (
        asyncio.create_task(execute_generation_items_forever())
        if settings.toapis_api_key is not None
        else None
    )
    try:
        yield
    finally:
        reconcile_task.cancel()
        offline_reconcile_task.cancel()
        retention_task.cancel()
        schedule_task.cancel()
        if generation_task is not None:
            generation_task.cancel()
        with suppress(asyncio.CancelledError):
            await reconcile_task
        with suppress(asyncio.CancelledError):
            await offline_reconcile_task
        with suppress(asyncio.CancelledError):
            await retention_task
        with suppress(asyncio.CancelledError):
            await schedule_task
        if generation_task is not None:
            with suppress(asyncio.CancelledError):
                await generation_task


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
    application.include_router(audit_log_router)
    application.include_router(ai_workbench_router)
    application.include_router(ai_model_admin_router)
    application.include_router(ai_model_catalog_router)
    application.include_router(authentication_router)
    application.include_router(assets_router)
    application.include_router(automation_apps_router)
    application.include_router(automation_parameter_preset_management_router)
    application.include_router(automation_parameter_presets_router)
    application.include_router(users_router)
    application.include_router(shops_router)
    application.include_router(devices_router)
    application.include_router(notifications_router)
    application.include_router(credentials_router)
    application.include_router(sessions_router)
    application.include_router(tasks_router)
    application.include_router(schedules_router)
    application.include_router(workers_router)
    application.include_router(worker_tasks_router)
    return application


app = create_app()
