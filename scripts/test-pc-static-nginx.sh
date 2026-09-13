#!/usr/bin/env bash
set -euo pipefail
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${1:?built production frontend image required}"
source "$repository_root/deploy/production/pc-static-assets.sh"
test_root="$(mktemp -d)"
container=""
trap 'if [[ -n "$container" ]]; then docker rm -f "$container" >/dev/null; fi; rm -rf -- "$test_root"' EXIT
mkdir -p "$test_root/old"
legacy_source="${2:-$test_root/old}"
if [[ $# -lt 2 ]]; then
    printf 'export default "legacy task";\n' > "$test_root/old/TaskCenterPage-Dbj5npBW.js"
    printf 'export default "legacy device";\n' > "$test_root/old/DeviceCenterPage-C5kRLAza.js"
    printf 'export default "legacy ai";\n' > "$test_root/old/AiGeneratePage-FvqWaXpb.js"
    printf '.old{color:red}\n' > "$test_root/old/page-12345678.css"
fi
pc_assets_import "$test_root/store" f6253bc7fb1ca9cef76219e9ff6915d22b0ea3b8 "$legacy_source"
container="$(docker run -d --read-only -p 127.0.0.1::18080 \
    --tmpfs /etc/nginx/conf.d --tmpfs /var/cache/nginx --tmpfs /var/run --tmpfs /tmp \
    -v "$test_root/store/public:/var/lib/control-center-static:ro" \
    -e FRONTEND_BIND_HOST=0.0.0.0 -e FRONTEND_BIND_PORT=18080 -e BACKEND_BIND_PORT=18001 \
    -e 'NGINX_ENVSUBST_FILTER=^(FRONTEND_BIND_HOST|FRONTEND_BIND_PORT|BACKEND_BIND_PORT)$' "$image")"
port="$(docker port "$container" 18080/tcp | cut -d: -f2)"
origin="http://127.0.0.1:$port"
for _ in $(seq 1 30); do
    if curl -fsS "$origin/" -o "$test_root/index.html" 2>/dev/null; then break; fi
    sleep 1
done
test -s "$test_root/index.html"
curl -fsSI "$origin/" | tr -d '\r' | grep -Fi 'Cache-Control: no-store'
while IFS= read -r -d '' asset; do
    relative="${asset#"$test_root/store/public/"}"
    curl -fsS "$origin/$relative" -o "$test_root/download"
    cmp "$asset" "$test_root/download"
done < <(find "$test_root/store/public/assets" -type f -print0)
for asset in /assets/missing-12345678.js /missing.js /assets/missing-12345678.css; do
    test "$(curl -sS -o "$test_root/missing" -w '%{http_code}' "$origin$asset")" = 404
    ! cmp -s "$test_root/index.html" "$test_root/missing"
done
# Simulate an expired retained asset and verify real 404, not the SPA document.
expired="$(find "$test_root/store/public/assets" -type f -name '*.js' -print -quit)"
relative="${expired#"$test_root/store/public/"}"
rm -- "$expired"
test "$(curl -sS -o /dev/null -w '%{http_code}' "$origin/$relative")" = 404
printf 'PASS: production Nginx retained asset bytes, cache headers and missing/expired script 404\n'
