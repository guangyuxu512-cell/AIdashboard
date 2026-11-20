#!/usr/bin/env bash
set -euo pipefail
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${1:?built production frontend image required}"
source "$repository_root/deploy/production/pc-static-assets.sh"
test_root="$(mktemp -d)"
container=""
upstream=""
trap 'if [[ -n "$upstream" ]]; then docker rm -f "$upstream" >/dev/null; fi; if [[ -n "$container" ]]; then docker rm -f "$container" >/dev/null; fi; rm -rf -- "$test_root"' EXIT
mkdir -p "$test_root/old"
legacy_source="${2:-$test_root/old}"
if [[ $# -lt 2 ]]; then
    printf 'export default "legacy task";\n' > "$test_root/old/TaskCenterPage-Dbj5npBW.js"
    printf 'export default "legacy device";\n' > "$test_root/old/DeviceCenterPage-C5kRLAza.js"
    printf 'export default "legacy ai";\n' > "$test_root/old/AiGeneratePage-FvqWaXpb.js"
    printf '.old{color:red}\n' > "$test_root/old/page-12345678.css"
fi
pc_assets_import "$test_root/store" f6253bc7fb1ca9cef76219e9ff6915d22b0ea3b8 "$legacy_source"
# Keep the reviewed rewrite and set directives unchanged. Only the upstream
# destination and transport are replaced for this isolated local fixture.
sed \
    -e 's|set \$token_admin_product_host pdc.mysiyuai.top;|set $token_admin_product_host 127.0.0.1:18081;|' \
    -e 's|proxy_pass https://\$token_admin_product_host|proxy_pass http://$token_admin_product_host|' \
    -e 's|proxy_pass http://127.0.0.1:18327|proxy_pass http://127.0.0.1:18081|' \
    -e 's|proxy_pass http://127.0.0.1:18521|proxy_pass http://127.0.0.1:18081|' \
    "$repository_root/frontend/deploy/default.conf.template" > "$test_root/proxy.template"
container="$(docker run -d --read-only -p 127.0.0.1::18080 \
    --tmpfs /etc/nginx/conf.d --tmpfs /var/cache/nginx --tmpfs /var/run --tmpfs /tmp \
    -v "$test_root/store/public:/var/lib/control-center-static:ro" \
    -v "$test_root/proxy.template:/etc/nginx/templates/default.conf.template:ro" \
    -e FRONTEND_BIND_HOST=0.0.0.0 -e FRONTEND_BIND_PORT=18080 -e BACKEND_BIND_PORT=18001 \
    -e 'NGINX_ENVSUBST_FILTER=^(FRONTEND_BIND_HOST|FRONTEND_BIND_PORT|BACKEND_BIND_PORT)$' "$image")"
port="$(docker port "$container" 18080/tcp | cut -d: -f2)"
origin="http://127.0.0.1:$port"
for _ in $(seq 1 30); do
    if curl -fsS "$origin/" -o "$test_root/index.html" 2>/dev/null; then break; fi
    sleep 1
done
test -s "$test_root/index.html"
install -d "$test_root/store/public/token-admin"
printf 'independent token admin release\n' > "$test_root/store/public/token-admin/index.html"
test "$(curl -sS "$origin/token-admin/")" = 'independent token admin release'
curl -sSI "$origin/token-manager/" | tr -d '\r' | grep -Fx 'Location: /token-admin/#centre'
cat > "$test_root/upstream.conf" <<'EOF'
pid /tmp/token-upstream.pid;
events {}
http {
    access_log off;
    server {
        listen 127.0.0.1:18081;
        location / {
            default_type text/plain;
            return 200 "$request_method|$uri|$args|$http_authorization|$http_cookie";
        }
    }
}
EOF
upstream="$(docker run -d --read-only --network "container:$container" --tmpfs /tmp --tmpfs /var/cache/nginx \
    -v "$test_root/upstream.conf:/etc/nginx/token-upstream.conf:ro" --entrypoint nginx "$image" \
    -c /etc/nginx/token-upstream.conf -g 'daemon off;')"
for _ in $(seq 1 30); do
    if curl -fsS "$origin/token-admin/_product/api/v1/tokens" -o /dev/null 2>/dev/null; then break; fi
    sleep 1
done
test "$(curl -fsS -H 'Authorization: Bearer fixture' -H 'Cookie: private=discard' "$origin/token-admin/_product/api/v1/tokens?fixture=1")" = \
    'GET|/api/v1/tokens|fixture=1|Bearer fixture|'
test "$(curl -fsS -X POST -H 'Authorization: Bearer fixture' -H 'Cookie: private=discard' "$origin/token-admin/_collector/collector-api/v1/admin/browsers/0123456789abcdef0123456789abcdef/submit-token/reveal")" = \
    'POST|/collector-api/v1/admin/browsers/0123456789abcdef0123456789abcdef/submit-token/reveal||Bearer fixture|'
test "$(curl -sS -o /dev/null -w '%{http_code}' "$origin/token-admin/_product/api/v1/products")" = 404
test "$(curl -sS -o /dev/null -w '%{http_code}' "$origin/token-admin/_collector/collector-api/v1/tasks")" = 404
test "$(curl -fsS -H 'Authorization: Bearer fixture' -H 'Cookie: private=discard' "$origin/token-admin/_operations/api/v1/tokens?fixture=1")" = \
    'GET|/api/v1/tokens|fixture=1|Bearer fixture|'
test "$(curl -sS -o /dev/null -w '%{http_code}' "$origin/token-admin/_operations/api/v1/candidates")" = 404
test "$(curl -fsS -H 'Authorization: Bearer fixture' -H 'Cookie: private=discard' "$origin/operations/api/v1/strategies")" = \
    'GET|/api/v1/strategies||Bearer fixture|'
test "$(curl -fsS -X POST -H 'Authorization: Bearer fixture' "$origin/operations/internal/worker/v1/selection-results/one")" = \
    'POST|/internal/worker/v1/selection-results/one||Bearer fixture|'
install -d "$test_root/store/public/operations"
printf 'independent operations release\n' > "$test_root/store/public/operations/index.html"
test "$(curl -sS "$origin/operations/")" = 'independent operations release'
test "$(curl -sS -o /dev/null -w '%{http_code}' "$origin/operations/missing.js")" = 404
test "$(curl -sS -o /dev/null -w '%{http_code}' "$origin/token-admin/missing.js")" = 404
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
