from fastapi import FastAPI

from app.core.exceptions import install_exception_handlers
from app.core.health import router as health_router
from app.modules.credentials.api import router as credentials_router
from app.modules.devices.api import router as devices_router
from app.modules.sessions.api import router as sessions_router
from app.modules.shops.api import router as shops_router
from app.modules.users.api import router as users_router


def create_app() -> FastAPI:
    application = FastAPI(title="Ecommerce AI Control Center Backend")
    install_exception_handlers(application)
    application.include_router(health_router)
    application.include_router(users_router)
    application.include_router(shops_router)
    application.include_router(devices_router)
    application.include_router(credentials_router)
    application.include_router(sessions_router)
    return application


app = create_app()
