import asyncio

from httpx import ASGITransport, AsyncClient

from app.main import create_app


def test_ai_file_routes_require_human_authentication_before_database() -> None:
    async def exercise() -> None:
        async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://testserver") as client:
            for resource in ("content", "thumbnail"):
                response = await client.get(f"/api/v1/ai-workbench/assets/00000000-0000-4000-8000-000000000001/{resource}")
                assert response.status_code == 401
                assert response.json()["code"] == "HUMAN_AUTHENTICATION_REQUIRED"
    asyncio.run(exercise())
