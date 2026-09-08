#!/usr/bin/env bash
set -euo pipefail

remote_root="${1:?production deployment root is required}"
archive_path="${2:?release archive path is required}"
release_sha="${3:?release SHA is required}"

if [[ "$remote_root" != "/opt/ecommerce-control-center/production" ]]; then
    echo "Refusing an unexpected production deployment root" >&2
    exit 2
fi
if [[ ! "$release_sha" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Production deployment requires a full lowercase Git commit SHA" >&2
    exit 2
fi
if [[ ! -f "$archive_path" ]]; then
    echo "Production release archive is missing" >&2
    exit 2
fi

release_directory="$remote_root/releases/$release_sha"
previous_release=""
deployment_succeeded=false
release_directory_created=false
deployment_runtime_changed=false
environment_file=""
nginx_target=""
nginx_backup=""

restore_previous_release() {
    if [[ -z "$environment_file" || -z "$previous_release" || ! -d "$previous_release" ]]; then
        # This function is called from the EXIT trap after a failed deployment.
        # Do not let a bare return reuse that failure status and short-circuit the
        # remaining cleanup for the release created by this attempt.
        return 0
    fi
    local previous_sha
    previous_sha="$(basename "$previous_release")"
    DEPLOYMENT_IMAGE_TAG="$previous_sha" docker compose \
        --project-name control-center-production \
        --env-file "$environment_file" \
        -f "$previous_release/deploy/production/compose.yaml" \
        up -d douyin-signer backend frontend >/dev/null 2>&1 || true
    ln -sfn "$previous_release" "$remote_root/current"
}

release_directory_is_current() {
    local active_release
    active_release="$(readlink -f "$remote_root/current" 2>/dev/null || true)"
    [[ "$active_release" == "$release_directory" ]]
}

cleanup() {
    rm -f -- "$archive_path"
    if [[ "$deployment_succeeded" != "true" ]]; then
        if [[ "$deployment_runtime_changed" == "true" ]]; then
            restore_previous_release
        fi
        if [[ "$release_directory_created" == "true" ]] && ! release_directory_is_current; then
            rm -rf -- "$release_directory"
        fi
    fi
}
trap cleanup EXIT

if [[ -L "$remote_root/current" ]]; then
    previous_release="$(readlink -f "$remote_root/current")"
fi
if [[ -e "$release_directory" ]]; then
    active_release="$(readlink -f "$remote_root/current" 2>/dev/null || true)"
    if [[ "$active_release" == "$release_directory" ]]; then
        echo "Production release is already active for this commit; skipping"
        exit 0
    fi
    echo "Production release already exists for this commit" >&2
    exit 2
fi

install -d -m 0750 "$remote_root" "$remote_root/releases" "$release_directory"
release_directory_created=true
tar -xzf "$archive_path" -C "$release_directory"

for required_path in \
    .dockerignore \
    package.json \
    pnpm-lock.yaml \
    pnpm-workspace.yaml \
    electron/package.json \
    mobile/package.json \
    backend/Dockerfile \
    backend/compose.yaml \
    backend/pyproject.toml \
    backend/alembic.ini \
    backend/app \
    backend/migrations \
    backend/douyin-signer \
    frontend/Dockerfile \
    frontend/deploy/default.conf.template \
    deploy/production/compose.yaml \
    deploy/production/host-nginx.conf.template \
    scripts/production-env.sh; do
    if [[ ! -e "$release_directory/$required_path" ]]; then
        echo "Production release is missing $required_path" >&2
        exit 2
    fi
done

source "$release_directory/scripts/production-env.sh"
environment_file="$remote_root/.env"
production_env_open "$environment_file"

required_environment=(
    BACKEND_DATABASE_URL
    BACKEND_ENCRYPTION_KEY
    BACKEND_DOUYIN_SIGNER_API_KEY
    BACKEND_DOUYIN_SIGNER_URL
    BACKEND_TOAPIS_API_KEY
    PRODUCTION_DOMAIN
    PRODUCTION_TLS_CERTIFICATE_PATH
    PRODUCTION_TLS_CERTIFICATE_KEY_PATH
    PRODUCTION_NGINX_VHOST_DIR
    PRODUCTION_ACME_WEBROOT_DIR
)
for key in "${required_environment[@]}"; do
    production_env_load_required "$key"
done

BACKEND_HUMAN_SESSION_COOKIE_SECURE="$(production_env_read BACKEND_HUMAN_SESSION_COOKIE_SECURE || true)"
BACKEND_BIND_PORT="$(production_env_read BACKEND_BIND_PORT || printf '18001')"
DOUYIN_SIGNER_BIND_PORT="$(production_env_read DOUYIN_SIGNER_BIND_PORT || printf '8788')"
FRONTEND_BIND_PORT="$(production_env_read FRONTEND_BIND_PORT || printf '18080')"
export PRODUCTION_DOMAIN PRODUCTION_TLS_CERTIFICATE_PATH PRODUCTION_TLS_CERTIFICATE_KEY_PATH PRODUCTION_ACME_WEBROOT_DIR
export BACKEND_BIND_PORT DOUYIN_SIGNER_BIND_PORT FRONTEND_BIND_PORT
nginx_target="$PRODUCTION_NGINX_VHOST_DIR/control-center-production.conf"

if [[ "$BACKEND_DATABASE_URL" != *"/control_center_prod"* ]]; then
    echo "Production backend must target the independent control_center_prod database" >&2
    exit 2
fi
if [[ "${BACKEND_HUMAN_SESSION_COOKIE_SECURE:-}" != "true" ]]; then
    echo "Production human session cookies must be secure" >&2
    exit 2
fi
if [[ "${BACKEND_DOUYIN_SIGNER_URL}" != "http://127.0.0.1:${DOUYIN_SIGNER_BIND_PORT:-8788}" ]]; then
    echo "Production Douyin signer must remain on its configured loopback port" >&2
    exit 2
fi
if [[ ! -f "$PRODUCTION_TLS_CERTIFICATE_PATH" || ! -f "$PRODUCTION_TLS_CERTIFICATE_KEY_PATH" ]]; then
    echo "Production TLS certificate files are unavailable; run the public-IP TLS provisioning workflow first" >&2
    exit 2
fi
if [[ ! -d "$PRODUCTION_NGINX_VHOST_DIR" ]]; then
    echo "Configured production Nginx vhost directory is unavailable" >&2
    exit 2
fi

for command in curl docker envsubst nginx tar; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Production host is missing required command: $command" >&2
        exit 2
    fi
done
if ! docker compose version >/dev/null 2>&1; then
    echo "Production host requires Docker Compose v2" >&2
    exit 2
fi

export DEPLOYMENT_IMAGE_TAG="$release_sha"
export PRODUCTION_ENV_FILE="$environment_file"
compose=(docker compose --project-name control-center-production --env-file "$environment_file" -f "$release_directory/deploy/production/compose.yaml")
"${compose[@]}" config -q
"${compose[@]}" build douyin-signer backend frontend
"${compose[@]}" run --rm --no-deps backend python -c \
    "from app.core.config import get_settings; from app.modules.assets.storage import verify_asset_storage; verify_asset_storage(get_settings()); print('asset-storage=ready')"
deployment_runtime_changed=true
"${compose[@]}" run --rm backend python -m alembic upgrade head

ln -sfn "$release_directory" "$remote_root/current"
"${compose[@]}" up -d douyin-signer backend frontend

wait_for_health() {
    local container_name="$1"
    for _ in $(seq 1 45); do
        local health
        health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_name" 2>/dev/null || true)"
        if [[ "$health" == "healthy" ]]; then
            return 0
        fi
        sleep 1
    done
    docker logs --tail 100 "$container_name" >&2 || true
    return 1
}

wait_for_http() {
    local url="$1"
    for _ in $(seq 1 45); do
        if curl --fail --silent --show-error "$url" >/dev/null; then
            return 0
        fi
        sleep 1
    done
    return 1
}

wait_for_health control-center-douyin-signer-prod
wait_for_health control-center-backend-prod
wait_for_http "http://127.0.0.1:${BACKEND_BIND_PORT:-18001}/health"
wait_for_http "http://127.0.0.1:${FRONTEND_BIND_PORT:-18080}/"

rendered_nginx="$release_directory/.control-center-production.conf"
envsubst '$PRODUCTION_DOMAIN $PRODUCTION_TLS_CERTIFICATE_PATH $PRODUCTION_TLS_CERTIFICATE_KEY_PATH $PRODUCTION_ACME_WEBROOT_DIR $FRONTEND_BIND_PORT' \
    < "$release_directory/deploy/production/host-nginx.conf.template" \
    > "$rendered_nginx"

if [[ -f "$nginx_target" ]]; then
    nginx_backup="$release_directory/.control-center-production.conf.previous"
    cp -- "$nginx_target" "$nginx_backup"
fi
install -m 0644 "$rendered_nginx" "$nginx_target"
if ! nginx -t; then
    if [[ -n "$nginx_backup" ]]; then
        install -m 0644 "$nginx_backup" "$nginx_target"
    else
        rm -f -- "$nginx_target"
    fi
    nginx -t >/dev/null 2>&1 || true
    echo "Production Nginx configuration validation failed; previous vhost was restored" >&2
    exit 1
fi
if ! nginx -s reload; then
    if [[ -n "$nginx_backup" ]]; then
        install -m 0644 "$nginx_backup" "$nginx_target"
        nginx -s reload || true
    else
        rm -f -- "$nginx_target"
        nginx -s reload || true
    fi
    echo "Production Nginx reload failed; previous vhost was restored when available" >&2
    exit 1
fi

"${compose[@]}" exec -T backend python -c \
    "from sqlalchemy import text; from app.core.database import get_database_engine; engine=get_database_engine(); connection=engine.connect(); print('database=' + connection.scalar(text('select current_database()'))); connection.close(); engine.dispose()"
"${compose[@]}" exec -T backend python -m alembic current

deployment_succeeded=true
echo "Production release $release_sha deployed"
