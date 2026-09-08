#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
deployment_script="$repository_root/scripts/remote-deploy-production.sh"
remote_root="/opt/ecommerce-control-center/production"
test_root="$(mktemp -d)"
test_root_created=false

cleanup_test_root() {
    rm -rf -- "$test_root"
    if [[ "$test_root_created" == "true" && -f "$remote_root/.control-center-cleanup-test" ]]; then
        sudo rm -rf -- "$remote_root"
    fi
}
trap cleanup_test_root EXIT

if [[ -e "$remote_root" ]]; then
    echo "Refusing to run cleanup ownership regression against an existing deployment root" >&2
    exit 1
fi

sudo install -d -m 0755 /opt/ecommerce-control-center
sudo install -d -m 0750 "$remote_root/releases"
sudo chown "$(id -u):$(id -g)" "$remote_root" "$remote_root/releases"
touch "$remote_root/.control-center-cleanup-test"
test_root_created=true

fake_bin="$test_root/bin"
docker_log="$test_root/docker.log"
mkdir -p "$fake_bin"
: > "$docker_log"
cat > "$fake_bin/docker" <<'EOF'
#!/usr/bin/env bash
printf 'unexpected docker invocation\n' >> "$TEST_DOCKER_LOG"
exit 99
EOF
cat > "$fake_bin/tar" <<'EOF'
#!/usr/bin/env bash
exit 99
EOF
cat > "$fake_bin/nginx" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$fake_bin/envsubst" <<'EOF'
#!/usr/bin/env bash
cat
EOF
chmod 0700 "$fake_bin/docker" "$fake_bin/tar" "$fake_bin/nginx" "$fake_bin/envsubst"
export TEST_DOCKER_LOG="$docker_log"

historical_sha="1111111111111111111111111111111111111111"
historical_release="$remote_root/releases/$historical_sha"
mkdir -p "$historical_release"
printf 'historical release marker\n' > "$historical_release/marker"
ln -s "$historical_release" "$remote_root/current"

existing_sha="2222222222222222222222222222222222222222"
existing_release="$remote_root/releases/$existing_sha"
mkdir -p "$existing_release"
printf 'existing release marker\n' > "$existing_release/marker"
existing_archive="$test_root/existing.tar.gz"
touch "$existing_archive"

set +e
PATH="$fake_bin:$PATH" bash "$deployment_script" "$remote_root" "$existing_archive" "$existing_sha" > "$test_root/existing.out" 2>&1
existing_status=$?
set -e

[[ "$existing_status" -eq 2 ]]
grep -Fqx 'Production release already exists for this commit' "$test_root/existing.out"
[[ -d "$existing_release" ]]
[[ -f "$existing_release/marker" ]]
[[ "$(readlink -f "$remote_root/current")" == "$historical_release" ]]
[[ ! -s "$docker_log" ]]

active_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
active_release="$remote_root/releases/$active_sha"
mkdir -p "$active_release"
printf 'active release marker\n' > "$active_release/marker"
active_archive="$test_root/active.tar.gz"
touch "$active_archive"
ln -sfn "$active_release" "$remote_root/current"

set +e
PATH="$fake_bin:$PATH" bash "$deployment_script" "$remote_root" "$active_archive" "$active_sha" > "$test_root/active.out" 2>&1
active_status=$?
set -e

[[ "$active_status" -eq 0 ]]
grep -Fqx 'Production release is already active for this commit; skipping' "$test_root/active.out"
[[ -d "$active_release" ]]
[[ -f "$active_release/marker" ]]
[[ ! -e "$active_archive" ]]
[[ "$(readlink -f "$remote_root/current")" == "$active_release" ]]
[[ ! -s "$docker_log" ]]
ln -sfn "$historical_release" "$remote_root/current"

new_sha="3333333333333333333333333333333333333333"
new_release="$remote_root/releases/$new_sha"
new_archive="$test_root/new.tar.gz"
touch "$new_archive"

set +e
PATH="$fake_bin:$PATH" bash "$deployment_script" "$remote_root" "$new_archive" "$new_sha" > "$test_root/new.out" 2>&1
new_status=$?
set -e

[[ "$new_status" -ne 0 ]]
[[ ! -e "$new_release" ]]
[[ -d "$historical_release" ]]
[[ -f "$historical_release/marker" ]]
[[ "$(readlink -f "$remote_root/current")" == "$historical_release" ]]
[[ ! -s "$docker_log" ]]

rm -- "$remote_root/current"

migration_source="$test_root/migration-source"
mkdir -p \
    "$migration_source/electron" \
    "$migration_source/mobile" \
    "$migration_source/backend/app" \
    "$migration_source/backend/migrations" \
    "$migration_source/backend/douyin-signer" \
    "$migration_source/frontend/deploy" \
    "$migration_source/deploy/production" \
    "$migration_source/scripts"
touch \
    "$migration_source/.dockerignore" \
    "$migration_source/package.json" \
    "$migration_source/pnpm-lock.yaml" \
    "$migration_source/pnpm-workspace.yaml" \
    "$migration_source/electron/package.json" \
    "$migration_source/mobile/package.json" \
    "$migration_source/backend/Dockerfile" \
    "$migration_source/backend/compose.yaml" \
    "$migration_source/backend/pyproject.toml" \
    "$migration_source/backend/alembic.ini" \
    "$migration_source/frontend/Dockerfile" \
    "$migration_source/frontend/deploy/default.conf.template" \
    "$migration_source/deploy/production/compose.yaml" \
    "$migration_source/deploy/production/host-nginx.conf.template"
cp "$repository_root/scripts/production-env.sh" "$migration_source/scripts/production-env.sh"

test_certificate="$test_root/fullchain.pem"
test_certificate_key="$test_root/privkey.pem"
test_nginx_vhost_dir="$test_root/nginx"
test_acme_webroot="$test_root/acme-webroot"
mounted_asset_source="$test_root/mounted-assets"
touch "$test_certificate" "$test_certificate_key"
mkdir -p "$test_nginx_vhost_dir" "$test_acme_webroot" "$mounted_asset_source"
printf 'control-center-asset-storage-v1\n' > "$mounted_asset_source/.control-center-asset-storage-v1"
cat > "$remote_root/.env" <<EOF
BACKEND_DATABASE_URL=postgresql+psycopg://placeholder:placeholder@127.0.0.1:35433/control_center_prod
BACKEND_ENCRYPTION_KEY=placeholder
BACKEND_HUMAN_SESSION_COOKIE_SECURE=true
BACKEND_DOUYIN_SIGNER_API_KEY=placeholder
BACKEND_DOUYIN_SIGNER_URL=http://127.0.0.1:8788
BACKEND_TOAPIS_API_KEY=placeholder
PRODUCTION_DOMAIN=203.0.113.1
PRODUCTION_TLS_CERTIFICATE_PATH=$test_certificate
PRODUCTION_TLS_CERTIFICATE_KEY_PATH=$test_certificate_key
PRODUCTION_NGINX_VHOST_DIR=$test_nginx_vhost_dir
PRODUCTION_ACME_WEBROOT_DIR=$test_acme_webroot
BACKEND_ASSET_STORAGE_MODE=mounted
BACKEND_ASSET_STORAGE_VOLUME_SOURCE=$mounted_asset_source
EOF

cat > "$fake_bin/tar" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
destination=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        -C)
            destination="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done
cp -a "$TEST_RELEASE_SOURCE/." "$destination/"
EOF
cat > "$fake_bin/docker" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$TEST_DOCKER_LOG"
if [[ "$*" == *" run --rm backend python -m alembic upgrade head" ]]; then
    exit 61
fi
exit 0
EOF
cat > "$fake_bin/findmnt" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "${TEST_FINDMNT_FSTYPE:-cifs}"
EOF
chmod 0700 "$fake_bin/docker" "$fake_bin/tar" "$fake_bin/findmnt"

migration_sha="4444444444444444444444444444444444444444"
migration_release="$remote_root/releases/$migration_sha"
migration_archive="$test_root/migration.tar.gz"
touch "$migration_archive"
: > "$docker_log"
export TEST_RELEASE_SOURCE="$migration_source"
export TEST_FINDMNT_FSTYPE=cifs

set +e
PATH="$fake_bin:$PATH" bash "$deployment_script" "$remote_root" "$migration_archive" "$migration_sha" > "$test_root/migration.out" 2>&1
migration_status=$?
set -e

[[ "$migration_status" -eq 61 ]]
[[ ! -e "$migration_release" ]]
[[ ! -e "$remote_root/current" ]]
[[ -d "$historical_release" ]]
[[ -f "$historical_release/marker" ]]
grep -F -- 'run --rm --no-deps backend python -c' "$docker_log"
grep -Fqx 'compose --project-name control-center-production --env-file /opt/ecommerce-control-center/production/.env -f /opt/ecommerce-control-center/production/releases/4444444444444444444444444444444444444444/deploy/production/compose.yaml run --rm backend python -m alembic upgrade head' "$docker_log"

local_asset_source="$test_root/local-assets"
mkdir -p "$local_asset_source"
printf 'control-center-asset-storage-v1\n' > "$local_asset_source/.control-center-asset-storage-v1"
sed -i "s|^BACKEND_ASSET_STORAGE_VOLUME_SOURCE=.*|BACKEND_ASSET_STORAGE_VOLUME_SOURCE=$local_asset_source|" "$remote_root/.env"
export TEST_FINDMNT_FSTYPE=ext4

local_source_sha="5555555555555555555555555555555555555555"
local_source_release="$remote_root/releases/$local_source_sha"
local_source_archive="$test_root/local-source.tar.gz"
touch "$local_source_archive"
: > "$docker_log"

set +e
PATH="$fake_bin:$PATH" bash "$deployment_script" "$remote_root" "$local_source_archive" "$local_source_sha" > "$test_root/local-source.out" 2>&1
local_source_status=$?
set -e

[[ "$local_source_status" -ne 0 ]]
[[ ! -e "$local_source_release" ]]
grep -Fqx 'Mounted asset storage host source is not a supported network mount' "$test_root/local-source.out"
! grep -F ' build ' "$docker_log"
! grep -F ' run --rm' "$docker_log"

echo 'Production release cleanup ownership regression passed'
