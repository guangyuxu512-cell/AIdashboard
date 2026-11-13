from fastapi.routing import APIRoute

from app.main import create_app
from app.modules.access.dependencies import get_actor_context
from app.modules.api_tokens.catalog import permissions_catalog
from app.modules.api_tokens.team_scope import TEAM_SCOPED_OPERATIONS


def _dependency_calls(dependency):
    result = {dependency.call}
    for child in dependency.dependencies:
        result.update(_dependency_calls(child))
    return result


def test_scoped_catalog_requires_existing_team_actor_and_excludes_worker_protocols():
    app = create_app()
    catalog = permissions_catalog(app)
    permissions = {item["id"] for item in catalog}
    scoped = {item["id"] for item in catalog if item["team_scoped"]}
    assert scoped == TEAM_SCOPED_OPERATIONS
    assert {"GET /api/v1/devices", "GET /api/v1/tasks", "POST /api/v1/tasks", "GET /api/v1/schedules"} <= permissions
    assert all("/api/v1/worker/" not in item for item in permissions)
    assert all("/api/v1/api-tokens" not in item for item in permissions)
    schema = app.openapi()
    assert schema["components"]["securitySchemes"]["CentralAiToken"]["scheme"] == "bearer"
    assert {"CentralAiToken": []} in schema["paths"]["/api/v1/tasks"]["get"]["security"]

    checked = set()
    for included in app.routes:
        router = getattr(included, "original_router", None)
        routes = router.routes if router is not None else [included]
        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            for method in route.methods:
                permission = f"{method} {route.path}"
                if permission in scoped:
                    assert get_actor_context in _dependency_calls(route.dependant), permission
                    checked.add(permission)
    assert checked == scoped
