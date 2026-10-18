#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${1:?baseline CI image tag is required}"
test_root="$(mktemp -d)"
updated_image="control-center-backend-cache-test:$(basename "$test_root" | tr '[:upper:]' '[:lower:]')"
cleanup() {
    docker image rm "$updated_image" >/dev/null 2>&1 || true
    rm -rf -- "$test_root"
}
trap cleanup EXIT

mkdir "$test_root/context"
# Export committed source, excluding local virtualenvs, secrets and artifacts.
git -C "$repository_root" archive HEAD backend | tar -xf - --strip-components=1 -C "$test_root/context"
docker build --no-cache --progress=plain --tag "$image" "$test_root/context" 2>&1 | tee "$test_root/cold.log"
docker run --rm --network none --workdir /tmp "$image" python -c \
    'import app, importlib.metadata as m; assert "/site-packages/" in app.__file__; assert m.version("ecommerce-control-backend"); print("installed-project=ready")'
docker run --rm --network none --workdir /tmp "$image" python -m pip check

printf 'value = "source-only-update"\n' > "$test_root/context/app/_dependency_cache_probe.py"
docker build --progress=plain --tag "$updated_image" "$test_root/context" 2>&1 | tee "$test_root/warm.log"

dependency_step="$(grep -E '^#[0-9]+ \[[^]]+\] RUN .*python -c ' "$test_root/warm.log" | tail -1 | cut -d' ' -f1)"
[[ -n "$dependency_step" ]]
grep -Fqx "$dependency_step CACHED" "$test_root/warm.log"
project_step="$(grep -E '^#[0-9]+ \[[^]]+\] RUN .*python -m pip install --no-deps --no-build-isolation \.' "$test_root/warm.log" | tail -1 | cut -d' ' -f1)"
[[ -n "$project_step" ]]
! grep -Fqx "$project_step CACHED" "$test_root/warm.log"
grep -Eq "^$project_step DONE( |$)" "$test_root/warm.log"

# The production USER app and /tmp ensure this comes from the installed wheel,
# rather than the copied /app source tree masking a stale installation.
docker run --rm --network none --workdir /tmp "$updated_image" python -c \
    'import os; from app import _dependency_cache_probe as p; assert os.getuid() != 0; assert p.value == "source-only-update"; assert "/site-packages/" in p.__file__; print("source-only-update=installed; dependency-step=cached; project-build=offline")'
echo 'Backend dependency cache and offline source-only rebuild regression passed'
