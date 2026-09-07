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

environment_file="$remote_root/.env"
if [[ ! -f "$environment_file" ]]; then
    echo "Production environment file is missing" >&2
    exit 2
fi

read_environment_value() {
    local key="$1"
    local line=""
    line="$(grep -m1 -E "^${key}=" "$environment_file" || true)"
    if [[ -z "$line" ]]; then
        return 1
    fi
    local value="${line#*=}"
    if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
        value="${value:1:${#value}-2}"
    fi
    printf '%s' "$value"
}

# Do not source the server .env: a database password may legitimately contain
# shell metacharacters. Docker Compose reads that file itself; this script only
# reads the specific deployment facts it must validate or render.
load_required_environment_value() {
    local key="$1"
    local value=""
    if ! value="$(read_environment_value "$key")" || [[ -z "$value" ]]; then
        echo "Production environment is missing $key" >&2
        exit 2
    fi
    printf -v "$key" '%s' "$value"
}

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
)
for key in "${required_environment[@]}"; do
    load_required_environment_value "$key"
done

BACKEND_HUMAN_SESSION_COOKIE_SECURE="$(read_environment_value BACKEND_HUMAN_SESSION_COOKIE_SECURE || true)"
BACKEND_BIND_PORT="$(read_environment_value BACKEND_BIND_PORT || printf '18001')"
DOUYIN_SIGNER_BIND_PORT="$(read_environment_value DOUYIN_SIGNER_BIND_PORT || printf '8788')"
FRONTEND_BIND_PORT="$(read_environment_value FRONTEND_BIND_PORT || printf '18080')"
export PRODUCTION_DOMAIN PRODUCTION_TLS_CERTIFICATE_PATH PRODUCTION_TLS_CERTIFICATE_KEY_PATH
export BACKEND_BIND_PORT DOUYIN_SIGNER_BIND_PORT FRONTEND_BIND_PORT

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
    echo "Production TLS certificate files are unavailable" >&2
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

release_directory="$remote_root/releases/$release_sha"
previous_release=""
deployment_succeeded=false
nginx_target="$PRODUCTION_NGINX_VHOST_DIR/control-center-production.conf"
nginx_backup=""

restore_previous_release() {
    if [[ -z "$previous_release" || ! -d "$previous_release" ]]; then
        return
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

cleanup() {
    rm -f -- "$archive_path"
    if [[ "$deployment_succeeded" != "true" ]]; then
        restore_previous_release
        rm -rf -- "$release_directory"
    fi
}
trap cleanup EXIT

if [[ -L "$remote_root/current" ]]; then
    previous_release="$(readlink -f "$remote_root/current")"
fi
if [[ -e "$release_directory" ]]; then
    echo "Production release already exists for this commit" >&2
    exit 2
fi

install -d -m 0750 "$remote_root" "$remote_root/releases" "$release_directory"
tar -xzf "$archive_path" -C "$release_directory"

for required_path in \
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
    deploy/production/host-nginx.conf.template; do
    if [[ ! -e "$release_directory/$required_path" ]]; then
        echo "Production release is missing $required_path" >&2
        exit 2
    fi
done

export DEPLOYMENT_IMAGE_TAG="$release_sha"
export PRODUCTION_ENV_FILE="$environment_file"
compose=(docker compose --project-name control-center-production --env-file "$environment_file" -f "$release_directory/deploy/production/compose.yaml")
"${compose[@]}" config -q
"${compose[@]}" build douyin-signer backend frontend
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

wait_for_health control-center-douyin-signer-prod
wait_for_health control-center-backend-prod
curl --fail --silent --show-error "http://127.0.0.1:${BACKEND_BIND_PORT:-18001}/health" >/dev/null
curl --fail --silent --show-error "http://127.0.0.1:${FRONTEND_BIND_PORT:-18080}/" >/dev/null

rendered_nginx="$release_directory/.control-center-production.conf"
envsubst '$PRODUCTION_DOMAIN $PRODUCTION_TLS_CERTIFICATE_PATH $PRODUCTION_TLS_CERTIFICATE_KEY_PATH $FRONTEND_BIND_PORT' \
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
