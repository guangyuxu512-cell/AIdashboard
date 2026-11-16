"""One permission per existing management API operation.

The catalog comes from the application's own OpenAPI contract, not URL guesses.
Device and application identities remain separate and are deliberately excluded.
"""

MANAGEMENT_TAGS = {
    "access", "access-management", "ai-workbench", "ai-model-management",
    "shop-onboarding", "assets", "automation-app-configs",
    "automation-parameter-presets", "users", "shops", "devices",
    "notification-channels", "operating-dashboard", "product-selection",
    "product-collection", "product-data", "credentials", "sessions",
    "tasks", "schedules",
}

from app.modules.api_tokens.team_scope import TEAM_SCOPED_OPERATIONS

METHODS = {"get", "post", "put", "patch", "delete"}


def _is_management_operation(path: str, method: str, detail: dict) -> bool:
    tag = (detail.get("tags") or [""])[0]
    return tag in MANAGEMENT_TAGS or (method == "get" and path == "/api/v1/auth/me")


def install_openapi_security(app, cookie_name: str) -> None:
    original = app.openapi

    def openapi():
        schema = original()
        schemes = schema.setdefault("components", {}).setdefault("securitySchemes", {})
        schemes["CentralAiToken"] = {"type": "http", "scheme": "bearer", "bearerFormat": "opaque"}
        schemes["CentralHumanSession"] = {"type": "apiKey", "in": "cookie", "name": cookie_name}
        for path, operations in schema.get("paths", {}).items():
            if not path.startswith("/api/v1/"):
                continue
            for method, detail in operations.items():
                if method in METHODS and _is_management_operation(path, method, detail):
                    detail["security"] = [{"CentralAiToken": []}, {"CentralHumanSession": []}]
                elif method in METHODS and (detail.get("tags") or [""])[0] == "api-tokens":
                    detail["security"] = [{"CentralHumanSession": []}]
        return schema

    app.openapi = openapi


def permissions_catalog(app) -> list[dict]:
    entries = []
    for path, operations in app.openapi().get("paths", {}).items():
        if not path.startswith("/api/v1/"):
            continue
        for method, detail in operations.items():
            if method not in METHODS:
                continue
            tag = (detail.get("tags") or [""])[0]
            if not _is_management_operation(path, method, detail):
                continue
            entries.append({
                "id": f"{method.upper()} {path}",
                "module": tag,
                "name": detail.get("summary") or detail.get("operationId") or path,
                "team_scoped": f"{method.upper()} {path}" in TEAM_SCOPED_OPERATIONS,
            })
    return sorted(entries, key=lambda entry: (entry["module"], entry["id"]))
