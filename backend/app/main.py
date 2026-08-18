from fastapi import FastAPI

from app.core.health import router as health_router


def create_app() -> FastAPI:
    application = FastAPI(title="Ecommerce AI Control Center Backend")
    application.include_router(health_router)
    return application


app = create_app()
