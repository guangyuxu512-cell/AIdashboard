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
chmod 0700 "$fake_bin/docker" "$fake_bin/tar"
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
PATH="$fake_bin:$PATH" "$deployment_script" "$remote_root" "$existing_archive" "$existing_sha" > "$test_root/existing.out" 2>&1
existing_status=$?
set -e

[[ "$existing_status" -eq 2 ]]
grep -Fqx 'Production release already exists for this commit' "$test_root/existing.out"
[[ -d "$existing_release" ]]
[[ -f "$existing_release/marker" ]]
[[ "$(readlink -f "$remote_root/current")" == "$historical_release" ]]
[[ ! -s "$docker_log" ]]

new_sha="3333333333333333333333333333333333333333"
new_release="$remote_root/releases/$new_sha"
new_archive="$test_root/new.tar.gz"
touch "$new_archive"

set +e
PATH="$fake_bin:$PATH" "$deployment_script" "$remote_root" "$new_archive" "$new_sha" > "$test_root/new.out" 2>&1
new_status=$?
set -e

[[ "$new_status" -ne 0 ]]
[[ ! -e "$new_release" ]]
[[ -d "$historical_release" ]]
[[ -f "$historical_release/marker" ]]
[[ "$(readlink -f "$remote_root/current")" == "$historical_release" ]]
[[ ! -s "$docker_log" ]]

echo 'Production release cleanup ownership regression passed'
