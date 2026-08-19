#!/usr/bin/env bash
set -euo pipefail

remote_root="${1:?remote root is required}"
archive_path="${2:?archive path is required}"
release_id="${3:?release id is required}"

if [[ "$remote_root" != "/opt/ecommerce-control-center/backend" ]]; then
    echo "Refusing unexpected deployment root" >&2
    exit 2
fi
if [[ ! "$release_id" =~ ^[0-9]{8}-[0-9]{6}-[a-f0-9]{7}$ ]]; then
    echo "Invalid release identifier" >&2
    exit 2
fi
if [[ ! -f "$remote_root/.env" ]]; then
    echo "Server environment file is missing" >&2
    exit 2
fi

release_directory="$remote_root/releases/$release_id"
deployment_succeeded=false
previous_release=""
if [[ -L "$remote_root/current" ]]; then
    previous_release="$(readlink -f "$remote_root/current")"
fi

cleanup_archive() {
    rm -f -- "$archive_path"
    if [[ "$deployment_succeeded" != "true" ]]; then
        active_release="$(readlink -f "$remote_root/current" 2>/dev/null || true)"
        if [[ "$active_release" == "$release_directory" ]]; then
            if [[ -n "$previous_release" && -f "$previous_release/.deploy.env" ]]; then
                ln -sfn "$previous_release" "$remote_root/current"
                docker compose --env-file "$previous_release/.deploy.env" \
                    -f "$previous_release/compose.yaml" up -d backend >/dev/null 2>&1 || true
            else
                rm -f -- "$remote_root/current"
            fi
        fi
        rm -rf -- "$release_directory"
    fi
}
trap cleanup_archive EXIT

if [[ -e "$release_directory" ]]; then
    echo "Release already exists" >&2
    exit 2
fi

install -d -m 0750 "$remote_root" "$remote_root/releases"
install -d -m 0750 "$release_directory"
tar -xzf "$archive_path" -C "$release_directory"
printf 'BACKEND_IMAGE_TAG=%s\n' "$release_id" > "$release_directory/.deploy.env"
chmod 0640 "$release_directory/.deploy.env"

for required in Dockerfile compose.yaml pyproject.toml alembic.ini app migrations; do
    if [[ ! -e "$release_directory/$required" ]]; then
        echo "Release is missing $required" >&2
        exit 2
    fi
done

compose=(docker compose --env-file "$release_directory/.deploy.env" -f "$release_directory/compose.yaml")
"${compose[@]}" build backend
"${compose[@]}" run --rm backend python -m alembic upgrade head

ln -sfn "$release_directory" "$remote_root/current"
"${compose[@]}" up -d backend

healthy=false
for _ in $(seq 1 30); do
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' control-center-backend-dev 2>/dev/null || true)"
    if [[ "$health" == "healthy" ]]; then
        healthy=true
        break
    fi
    sleep 1
done

if [[ "$healthy" != "true" ]]; then
    docker logs --tail 100 control-center-backend-dev >&2 || true
    if [[ -n "$previous_release" && -f "$previous_release/.deploy.env" ]]; then
        ln -sfn "$previous_release" "$remote_root/current"
        docker compose --env-file "$previous_release/.deploy.env" \
            -f "$previous_release/compose.yaml" up -d backend
    else
        rm -f -- "$remote_root/current"
        rm -rf -- "$release_directory"
    fi
    echo "Backend did not become healthy; previous release restored when available" >&2
    exit 1
fi

curl --fail --silent --show-error http://127.0.0.1:18000/health
echo
"${compose[@]}" exec -T backend python -c \
    "from sqlalchemy import text; from app.core.database import get_database_engine; e=get_database_engine(); c=e.connect(); print('database=' + c.scalar(text('select current_database()'))); print('postgresql=connected'); c.close(); e.dispose()"
"${compose[@]}" exec -T backend python -m alembic current

deployment_succeeded=true
echo "Backend release $release_id deployed"
