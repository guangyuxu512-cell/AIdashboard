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
    mobile/index.html \
    mobile/vite.config.ts \
    mobile/src/main.ts \
    mobile/public/manifest.webmanifest \
    mobile/public/icons/icon-192.png \
    mobile/public/icons/icon-512.png \
    mobile/public/icons/icon-maskable-512.png \
    mobile/public/icons/apple-touch-icon.png \
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
    deploy/production/pc-static-assets.sh \
    scripts/production-env.sh; do
    if [[ ! -e "$release_directory/$required_path" ]]; then
        echo "Production release is missing $required_path" >&2
        exit 2
    fi
done

source "$release_directory/scripts/production-env.sh"
source "$release_directory/deploy/production/pc-static-assets.sh"
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
BACKEND_ASSET_STORAGE_MODE="$(production_env_read BACKEND_ASSET_STORAGE_MODE || printf 'local')"
BACKEND_ASSET_STORAGE_VOLUME_SOURCE="$(production_env_read BACKEND_ASSET_STORAGE_VOLUME_SOURCE || true)"
PRODUCTION_BUILDX_BUILDER="$(production_env_read PRODUCTION_BUILDX_BUILDER || true)"
if [[ -n "$PRODUCTION_BUILDX_BUILDER" && ! "$PRODUCTION_BUILDX_BUILDER" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]*$ ]]; then
    echo "Production Buildx builder must be a single name containing only letters, digits, dots, underscores or hyphens" >&2
    exit 2
fi
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

verify_mounted_asset_storage_host_mount() {
    if [[ "$BACKEND_ASSET_STORAGE_MODE" == "local" ]]; then
        return 0
    fi
    if [[ "$BACKEND_ASSET_STORAGE_MODE" != "mounted" ]]; then
        echo "Production asset storage mode must be local or mounted" >&2
        return 1
    fi
    if [[ -z "$BACKEND_ASSET_STORAGE_VOLUME_SOURCE" || "$BACKEND_ASSET_STORAGE_VOLUME_SOURCE" != /* ]]; then
        echo "Mounted asset storage requires an absolute host mount source" >&2
        return 1
    fi
    if [[ ! -d "$BACKEND_ASSET_STORAGE_VOLUME_SOURCE" ]]; then
        echo "Mounted asset storage host source is unavailable" >&2
        return 1
    fi
    if ! command -v findmnt >/dev/null 2>&1; then
        echo "Mounted asset storage requires findmnt on the production host" >&2
        return 1
    fi

    local filesystem_type
    while IFS= read -r filesystem_type; do
        filesystem_type="${filesystem_type//[[:space:]]/}"
        case "$filesystem_type" in
            cifs|nfs|nfs4)
                return 0
                ;;
        esac
    done < <(findmnt --noheadings --output FSTYPE --target "$BACKEND_ASSET_STORAGE_VOLUME_SOURCE")

    echo "Mounted asset storage host source is not a supported network mount" >&2
    return 1
}

verify_mounted_asset_storage_host_mount

export DEPLOYMENT_IMAGE_TAG="$release_sha"
export PRODUCTION_ENV_FILE="$environment_file"
compose=(docker compose --project-name control-center-production --env-file "$environment_file" -f "$release_directory/deploy/production/compose.yaml")
"${compose[@]}" config -q
build_options=()
if [[ -n "$PRODUCTION_BUILDX_BUILDER" ]]; then
    build_options+=(--builder "$PRODUCTION_BUILDX_BUILDER")
fi
"${compose[@]}" build "${build_options[@]}" douyin-signer backend frontend
"${compose[@]}" run --rm --no-deps backend python -c \
    "from app.core.config import get_settings; from app.modules.assets.storage import verify_asset_storage; verify_asset_storage(get_settings()); print('asset-storage=ready')"

# Populate the shared read-only PC asset mount before replacing any service.
static_store="$remote_root/pc-static-assets"
if [[ ! -f "$static_store/.bootstrapped" ]]; then
    # First upgrade: import still-available historical release images, including
    # old windows' chunks. No historical HTML, API responses or env is exported.
    for historical_release in "$remote_root"/releases/*; do
        historical_sha="$(basename "$historical_release")"
        [[ "$historical_sha" =~ ^[0-9a-f]{40}$ && "$historical_sha" != "$release_sha" ]] || continue
        historical_image="ecommerce-control-center-frontend-prod:$historical_sha"
        if docker image inspect "$historical_image" >/dev/null 2>&1; then
            pc_assets_capture_image "$static_store" "$historical_sha" "$historical_image"
        else
            echo "Historical PC image unavailable for asset import: $historical_sha"
        fi
    done
fi
if [[ -n "$previous_release" ]]; then
    previous_sha="$(basename "$previous_release")"
    pc_assets_capture_image "$static_store" "$previous_sha" "ecommerce-control-center-frontend-prod:$previous_sha"
fi
pc_assets_capture_image "$static_store" "$release_sha" "ecommerce-control-center-frontend-prod:$release_sha"
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

verify_mobile_frontend() {
    local frontend_origin="http://127.0.0.1:${FRONTEND_BIND_PORT:-18080}"
    local mobile_document
    local mobile_redirect_headers
    local asset_path
    local -a asset_paths

    mobile_redirect_headers="$(
        curl --fail --silent --show-error --head \
            --header "Host: ${PRODUCTION_DOMAIN}" \
            --header 'X-Forwarded-Proto: https' \
            "$frontend_origin/mobile" |
            tr -d '\r'
    )"
    if ! printf '%s\n' "$mobile_redirect_headers" | grep -Eq '^HTTP/[0-9.]+ 308' ||
        ! printf '%s\n' "$mobile_redirect_headers" | grep -Eqi '^Location: /mobile/$'; then
        echo "Mobile /mobile must return 308 with the proxy-safe relative Location /mobile/" >&2
        return 1
    fi

    mobile_document="$(curl --fail --silent --show-error "$frontend_origin/mobile/")"
    if ! printf '%s' "$mobile_document" | grep -Eq '/mobile/assets/[^" ]+\.js' ||
        ! printf '%s' "$mobile_document" | grep -Eq '/mobile/assets/[^" ]+\.css'; then
        echo "Mobile production document is missing its built JS or CSS assets" >&2
        return 1
    fi
    mapfile -t asset_paths < <(
        printf '%s' "$mobile_document" |
            grep -Eo '/mobile/assets/[^" ]+\.(css|js)' |
            sort -u
    )
    if [[ "${#asset_paths[@]}" -lt 2 ]]; then
        echo "Mobile production document is missing its built JS or CSS assets" >&2
        return 1
    fi
    for asset_path in "${asset_paths[@]}"; do
        curl --fail --silent --show-error "$frontend_origin$asset_path" >/dev/null
    done

    curl --fail --silent --show-error "$frontend_origin/mobile/manifest.webmanifest" >/dev/null
    curl --fail --silent --show-error "$frontend_origin/mobile/icons/icon-192.png" >/dev/null
    curl --fail --silent --show-error "$frontend_origin/mobile/icons/icon-512.png" >/dev/null
}

wait_for_health control-center-douyin-signer-prod
wait_for_health control-center-backend-prod
wait_for_http "http://127.0.0.1:${BACKEND_BIND_PORT:-18001}/health"
wait_for_http "http://127.0.0.1:${FRONTEND_BIND_PORT:-18080}/"
wait_for_http "http://127.0.0.1:${FRONTEND_BIND_PORT:-18080}/mobile/"
verify_mobile_frontend

rendered_nginx="$release_directory/.control-center-production.conf"
envsubst '$PRODUCTION_DOMAIN $PRODUCTION_TLS_CERTIFICATE_PATH $PRODUCTION_TLS_CERTIFICATE_KEY_PATH $PRODUCTION_ACME_WEBROOT_DIR $BACKEND_BIND_PORT $FRONTEND_BIND_PORT' \
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
# Only successful activation advances retention/pruning. Failure cleanup never
# removes shared assets, and same-SHA retries return before touching metadata.
pc_assets_activate "$static_store" "$release_sha" "${previous_release##*/}"
touch "$static_store/.bootstrapped"
echo "Production release $release_sha deployed"
