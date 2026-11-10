#!/usr/bin/env bash
set -euo pipefail
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
frontend_image="${1:?built production frontend image required}"
backend_image="${2:?built production backend image required for the transport fixture}"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/asset-upload-proxy.XXXXXX")"
containers=()
cleanup() {
    status=$?
    for ((i=${#containers[@]}-1; i>=0; i--)); do
        if ((status != 0)); then docker logs "${containers[i]}" >&2 || true; fi
        docker rm -f "${containers[i]}" >/dev/null 2>&1 || true
    done
    rm -rf -- "$test_root"
}
trap cleanup EXIT
run_id="asset-upload-proxy-${test_root##*.}"
mkdir "$test_root/tls"
openssl req -x509 -newkey rsa:2048 -nodes -days 1 -subj '/CN=127.0.0.1' \
    -addext 'subjectAltName=IP:127.0.0.1' \
    -keyout "$test_root/tls/key.pem" -out "$test_root/tls/cert.pem" 2>/dev/null

# Deliberately configure body logging at the http level. The narrowly scoped
# signing locations must disable it regardless of inherited access-log format.
cat > "$test_root/nginx.conf" <<'NGINX'
worker_processes 1;
error_log /dev/stderr warn;
pid /tmp/nginx.pid;
events { worker_connections 1024; }
http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    log_format body_probe '$request_method $uri $request_body';
    access_log /dev/stdout body_probe;
    include /etc/nginx/conf.d/*.conf;
}
NGINX

# Use the production image/template and the same bounded writable mounts as Compose.
# Only this container publishes ports, both on randomly allocated host loopback ports.
frontend="$(docker run -d --name "$run_id-frontend" --read-only \
    -p 127.0.0.1::18080 -p 127.0.0.1::443 \
    -v "$test_root/nginx.conf:/etc/nginx/nginx.conf:ro" \
    --tmpfs /etc/nginx/conf.d:size=1m,mode=0755 \
    --tmpfs /var/cache/nginx:size=16m,mode=1777 \
    --tmpfs /var/run:size=1m,mode=1777 --tmpfs /tmp:size=16m,mode=1777 \
    -e FRONTEND_BIND_HOST=0.0.0.0 -e FRONTEND_BIND_PORT=18080 -e BACKEND_BIND_PORT=18001 \
    -e 'NGINX_ENVSUBST_FILTER=^(FRONTEND_BIND_HOST|FRONTEND_BIND_PORT|BACKEND_BIND_PORT)$' \
    "$frontend_image")"
containers+=("$frontend")

# This stdlib receiver runs no application code and stores only transport receipts in
# memory. Its multipart/hash checks do not prove image validation, access or NAS I/O.
receiver="$(docker run -d --name "$run_id-receiver" --read-only --no-healthcheck \
    --network "container:$frontend" --entrypoint python "$backend_image" -B -u -c '
import hashlib
import json
import re
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer

class Receiver(BaseHTTPRequestHandler):
    arrivals = 0

    def reply_bytes(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def reply(self, status, text, content_type="text/plain"):
        body = (text + "\n").encode()
        self.reply_bytes(status, body, content_type)

    def do_GET(self):
        if re.fullmatch(r"/api/v1/worker/tasks/[^/]+/precheck-sign/?(?:\?.*)?", self.path):
            return self.reply(405, json.dumps({"backend": "transport-fixture", "method": "GET"}), "application/json")
        if self.path == "/rpa/v1/product-images/00000000000000000000000000000000.png":
            if self.headers.get("Authorization") or self.headers.get("Cookie"):
                return self.reply(400, "public image request leaked credentials")
            return self.reply_bytes(200, b"\x89PNG\r\n\x1a\npublic-rpa-image-fixture", "image/png")
        if self.path.startswith("/internal/applications/v1/"):
            return self.reply(200, json.dumps({
                "backend": "transport-fixture", "path": self.path,
                "proto": self.headers.get("X-Forwarded-Proto"),
                "authorized": self.headers.get("Authorization") == "Bearer synthetic-proxy-token",
                "application": self.headers.get("X-Application-ID"),
            }), "application/json")
        self.reply(200, str(Receiver.arrivals))

    def do_POST(self):
        if re.fullmatch(r"/api/v1/worker/tasks/[^/]+/precheck-sign/?(?:\?.*)?", self.path):
            size = int(self.headers.get("Content-Length", "0"))
            authorized = self.headers.get("Authorization") == "Bearer synthetic-proxy-token"
            if self.headers.get("X-Streaming-Probe") == "1":
                first = self.rfile.read(1)
                return self.reply(200 if authorized and first == b"{" else 401,
                                  json.dumps({"streamed": bool(first)}), "application/json")
            body = self.rfile.read(size)
            return self.reply(200 if authorized else 401, json.dumps({
                "backend": "transport-fixture", "path": self.path, "method": "POST",
                "proto": self.headers.get("X-Forwarded-Proto"),
                "authorized": authorized, "device": self.headers.get("X-Device-ID"),
                "size": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            }), "application/json")
        if self.path.startswith("/internal/mobile-collection/v1/"):
            size = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(size).decode()
            authorized = self.headers.get("Authorization") == "Bearer synthetic-proxy-token"
            return self.reply(200 if authorized else 401, json.dumps({
                "backend": "transport-fixture", "path": self.path,
                "body": body, "authorized": authorized,
            }), "application/json")
        Receiver.arrivals += 1
        self.connection.settimeout(10)
        size = int(self.headers.get("Content-Length", "0"))
        if self.path != "/api/v1/assets" or not 0 < size < 14 * 1024 * 1024:
            return self.reply(400, "unexpected transport request")
        body = self.rfile.read(size)
        headers = "Content-Type: " + self.headers.get("Content-Type", "") + "\r\n\r\n"
        message = BytesParser(policy=policy.default).parsebytes(headers.encode() + body)
        parts = list(message.iter_parts())
        if len(body) != size or len(parts) != 1 or parts[0].get_param("name", header="content-disposition") != "file":
            return self.reply(400, "invalid multipart transport")
        payload = parts[0].get_payload(decode=True)
        self.reply(201, f"{Receiver.arrivals} {len(payload)} {hashlib.sha256(payload).hexdigest()} {size}")

    def log_message(self, *args):
        pass

HTTPServer(("127.0.0.1", 18001), Receiver).serve_forever()
')"
containers+=("$receiver")

# Render the unchanged host vhost with explicit test-only values, preserving Nginx
# variables. A trusted temporary IP certificate exercises TLS without curl -k.
docker run --rm -i --network none --read-only --entrypoint envsubst \
    -e PRODUCTION_DOMAIN=127.0.0.1 -e PRODUCTION_ACME_WEBROOT_DIR=/tmp/acme \
    -e PRODUCTION_TLS_CERTIFICATE_PATH=/test-tls/cert.pem \
    -e PRODUCTION_TLS_CERTIFICATE_KEY_PATH=/test-tls/key.pem \
    -e BACKEND_BIND_PORT=18001 -e FRONTEND_BIND_PORT=18080 \
    -e PRODUCT_LIBRARY_IMAGE_UPSTREAM=http://127.0.0.1:18001 \
    "$frontend_image" \
    '${PRODUCTION_DOMAIN} ${PRODUCTION_ACME_WEBROOT_DIR} ${PRODUCTION_TLS_CERTIFICATE_PATH} ${PRODUCTION_TLS_CERTIFICATE_KEY_PATH} ${BACKEND_BIND_PORT} ${FRONTEND_BIND_PORT} ${PRODUCT_LIBRARY_IMAGE_UPSTREAM}' \
    < "$repository_root/deploy/production/host-nginx.conf.template" > "$test_root/host.conf"
host="$(docker run -d --name "$run_id-host" --read-only \
    --network "container:$frontend" --entrypoint nginx \
    --tmpfs /var/cache/nginx:size=16m,mode=1777 \
    --tmpfs /var/run:size=1m,mode=1777 --tmpfs /tmp:size=16m,mode=1777 \
    -v "$test_root/nginx.conf:/etc/nginx/nginx.conf:ro" \
    -v "$test_root/host.conf:/etc/nginx/conf.d/default.conf:ro" \
    -v "$test_root/tls:/test-tls:ro" "$frontend_image" -g 'daemon off;')"
containers+=("$host")
http_origin="http://127.0.0.1:$(docker port "$frontend" 18080/tcp | cut -d: -f2)"
https_origin="https://127.0.0.1:$(docker port "$frontend" 443/tcp | cut -d: -f2)"
curl_options=(--noproxy '*' --silent --show-error --connect-timeout 2 --max-time 20)

for origin in "$http_origin" "$https_origin"; do
    trust=()
    if [[ "$origin" == https:* ]]; then trust=(--cacert "$test_root/tls/cert.pem"); fi
    ready=false
    for _ in $(seq 1 30); do
        if curl "${curl_options[@]}" "${trust[@]}" --max-time 2 --fail \
            "$origin/api/v1/assets" -o "$test_root/arrivals" 2>/dev/null; then
            ready=true
            break
        fi
        sleep 1
    done
    test "$ready" = true

    # Small, just above the old 1 MiB boundary, a reported failing size, and a full
    # 10 MiB file. The multipart envelope must also arrive intact at the receiver.
    for size in 1024 1048577 2726298 10485760; do
        truncate -s "$size" "$test_root/payload.bin"
        expected_hash="$(sha256sum "$test_root/payload.bin" | cut -d' ' -f1)"
        before="$(curl "${curl_options[@]}" "${trust[@]}" --fail "$origin/api/v1/assets")"
        code="$(curl "${curl_options[@]}" "${trust[@]}" -H 'Expect:' \
            -F "file=@$test_root/payload.bin;type=image/png" \
            -o "$test_root/receipt" -w '%{http_code}' "$origin/api/v1/assets")"
        test "$code" = 201
        read -r arrivals received_size received_hash body_size < "$test_root/receipt"
        test "$arrivals" = "$((before + 1))"
        test "$received_size" = "$size"
        test "$received_hash" = "$expected_hash"
        test "$body_size" -gt "$size"
        test "$body_size" -lt 12582912
    done

    # A 12 MiB file plus the multipart envelope exceeds the proxy body limit.
    # Count arrivals before reading bodies, so rejection also proves no forwarding.
    truncate -s 12582912 "$test_root/payload.bin"
    before="$(curl "${curl_options[@]}" "${trust[@]}" --fail "$origin/api/v1/assets")"
    code="$(curl "${curl_options[@]}" "${trust[@]}" \
        -F "file=@$test_root/payload.bin;type=image/png" \
        -o "$test_root/rejected" -w '%{http_code}' "$origin/api/v1/assets")"
    test "$code" = 413
    test "$(curl "${curl_options[@]}" "${trust[@]}" --fail "$origin/api/v1/assets")" = "$before"

    # Internal mobile endpoints must preserve the complete URI, query, body and
    # Authorization header. The fixture is not an application credential check.
    for path in \
        '/internal/mobile-collection/v1/attempts/register?scope=one%2Ftwo&replay=1' \
        '/internal/mobile-collection/v1/attempts/00000000-0000-0000-0000-000000000001/credentials/refresh'; do
        for auth in missing invalid valid; do
            auth_headers=()
            expected_code=401
            authorized=false
            if [[ "$auth" == invalid ]]; then
                auth_headers=(-H 'Authorization: Bearer invalid-proxy-token')
            elif [[ "$auth" == valid ]]; then
                auth_headers=(-H 'Authorization: Bearer synthetic-proxy-token')
                expected_code=200
                authorized=true
            fi
            code="$(curl "${curl_options[@]}" "${trust[@]}" "${auth_headers[@]}" \
                -H 'Content-Type: application/json' --data-binary '{"proxyFixture":true}' \
                -D "$test_root/internal.headers" -o "$test_root/internal.json" \
                -w '%{http_code}' "$origin$path")"
            test "$code" = "$expected_code"
            tr -d '\r' < "$test_root/internal.headers" | grep -Eqi '^Content-Type: application/json'
            expected="$(printf '{"backend": "transport-fixture", "path": "%s", "body": "{\\"proxyFixture\\":true}", "authorized": %s}\n' "$path" "$authorized")"
            test "$(cat "$test_root/internal.json")" = "$expected"
        done
    done

    # Do not expose a broader /internal/ or a different protocol-version prefix.
    curl "${curl_options[@]}" "${trust[@]}" --fail "$origin/index.html" -o "$test_root/pc.html"
    for path in /internal/mobile-collection/v2/attempts/register /internal/unrelated; do
        curl "${curl_options[@]}" "${trust[@]}" --fail "$origin$path" -o "$test_root/non-mobile.html"
        cmp "$test_root/pc.html" "$test_root/non-mobile.html"
    done
done

# The signing request is intentionally large enough that default proxy
# buffering may spill it to disk. The receipt carries only its digest/length.
python -c 'import json,sys; json.dump({"cookie":"SYNTHETIC_SIGN_BODY_SENTINEL" + "x" * 20000}, open(sys.argv[1],"w"), separators=(",",":"))' "$test_root/sign-body.json"
sign_path='/api/v1/worker/tasks/00000000-0000-0000-0000-000000000001/precheck-sign?scope=one%2Ftwo'
for origin in "$http_origin" "$https_origin"; do
    trust=()
    expected_proto=http
    if [[ "$origin" == https:* ]]; then
        trust=(--cacert "$test_root/tls/cert.pem")
        expected_proto=https
    fi
    for auth in missing invalid valid; do
        auth_headers=()
        expected_code=401
        if [[ "$auth" == invalid ]]; then auth_headers=(-H 'Authorization: Bearer invalid-proxy-token'); fi
        if [[ "$auth" == valid ]]; then
            auth_headers=(-H 'Authorization: Bearer synthetic-proxy-token')
            expected_code=200
        fi
        code="$(curl "${curl_options[@]}" "${trust[@]}" "${auth_headers[@]}" \
            -H 'X-Device-ID: synthetic-device' -H 'X-Forwarded-Proto: spoofed' \
            -H 'Content-Type: application/json' --data-binary "@$test_root/sign-body.json" \
            -o "$test_root/sign-receipt.json" -w '%{http_code}' "$origin$sign_path")"
        test "$code" = "$expected_code"
        python - "$test_root/sign-body.json" "$test_root/sign-receipt.json" "$sign_path" "$expected_proto" "$auth" <<'PY'
import hashlib, json, pathlib, sys
body = pathlib.Path(sys.argv[1]).read_bytes()
receipt = json.loads(pathlib.Path(sys.argv[2]).read_text())
assert receipt == {"backend": "transport-fixture", "path": sys.argv[3], "method": "POST",
    "proto": sys.argv[4], "authorized": sys.argv[5] == "valid", "device": "synthetic-device",
    "size": len(body), "sha256": hashlib.sha256(body).hexdigest()}
PY
    done
    code="$(curl "${curl_options[@]}" "${trust[@]}" -o "$test_root/sign-get.json" \
        -w '%{http_code}' "$origin$sign_path")"
    test "$code" = 405
    # A direct request to a sibling path remains an ordinary API request.
    code="$(curl "${curl_options[@]}" "${trust[@]}" -H 'Authorization: Bearer synthetic-proxy-token' \
        --data-binary '{"control":"SYNTHETIC_NON_SIGN_BODY"}' -o "$test_root/sibling.txt" -w '%{http_code}' \
        "$origin/api/v1/worker/tasks/00000000-0000-0000-0000-000000000001/precheck-sign-extra")"
    test "$code" = 400
done

# Hold the request body incomplete. Backend must still receive its first byte
# and answer; a buffering proxy waits for the full body and times out here.
python - "$http_origin" "$https_origin" "$test_root/tls/cert.pem" <<'PY'
import socket, ssl, sys
from urllib.parse import urlsplit
for origin in sys.argv[1:3]:
    parsed = urlsplit(origin)
    with socket.create_connection((parsed.hostname, parsed.port), timeout=3) as raw:
        sock = ssl.create_default_context(cafile=sys.argv[3]).wrap_socket(raw, server_hostname=parsed.hostname) if parsed.scheme == 'https' else raw
        sock.settimeout(3)
        sock.sendall(("POST /api/v1/worker/tasks/00000000-0000-0000-0000-000000000001/precheck-sign HTTP/1.1\r\n"
            "Host: 127.0.0.1\r\nAuthorization: Bearer synthetic-proxy-token\r\n"
            "X-Streaming-Probe: 1\r\nContent-Length: 20000\r\nConnection: close\r\n\r\n{").encode())
        response = sock.recv(1024)
        assert response.startswith(b'HTTP/1.1 200 '), 'signing request was not streamed to Backend'
PY
# Prove the deliberately unsafe inherited format is active for normal routes;
# the secret-specific assertions below would otherwise be vacuous.
for name in frontend host; do
    container="$frontend"
    if [[ "$name" == host ]]; then container="$host"; fi
    logged=false
    for _ in $(seq 1 10); do
        docker logs "$container" > "$test_root/$name.log" 2>&1
        if grep -q 'SYNTHETIC_NON_SIGN_BODY' "$test_root/$name.log"; then
            logged=true
            break
        fi
        sleep 0.1
    done
    test "$logged" = true
done
if grep -q 'SYNTHETIC_SIGN_BODY_SENTINEL' "$test_root/frontend.log"; then
    echo 'Sensitive request body appeared in frontend access logs' >&2
    exit 1
fi
if grep -q 'SYNTHETIC_SIGN_BODY_SENTINEL' "$test_root/host.log"; then
    echo 'Sensitive request body appeared in host access logs' >&2
    exit 1
fi

# Software Session access must use the host TLS proxy directly: the frontend
# proxy does not forward this prefix.  A spoofed incoming proto must be replaced
# by the trusted host TLS proxy before reaching the backend transport fixture.
app_path='/internal/applications/v1/shops/00000000-0000-0000-0000-000000000001/session?sample=1'
curl "${curl_options[@]}" --cacert "$test_root/tls/cert.pem" --fail \
    -H 'Authorization: Bearer synthetic-proxy-token' -H 'X-Application-ID: synthetic-app' \
    -H 'X-Forwarded-Proto: http' "$https_origin$app_path" -o "$test_root/app.json"
expected_app='{"backend": "transport-fixture", "path": "/internal/applications/v1/shops/00000000-0000-0000-0000-000000000001/session?sample=1", "proto": "https", "authorized": true, "application": "synthetic-app"}'
test "$(cat "$test_root/app.json")" = "$expected_app"
curl "${curl_options[@]}" --fail "$http_origin/index.html" -o "$test_root/http-index.html"
curl "${curl_options[@]}" --fail "$http_origin$app_path" -o "$test_root/http-app.html"
cmp "$test_root/http-index.html" "$test_root/http-app.html"

# Only the ProductDataCenter-owned image prefix is public.  The real NAS origin
# is replaced with the same in-memory receiver for this transport-only test.
image_path='/rpa/v1/product-images/00000000000000000000000000000000.png'
printf '\211PNG\r\n\032\npublic-rpa-image-fixture' > "$test_root/expected-product-image.png"
curl "${curl_options[@]}" --cacert "$test_root/tls/cert.pem" --fail \
    -H 'Authorization: Bearer must-not-reach-nas' -H 'Cookie: session=must-not-reach-nas' \
    -D "$test_root/product-image.headers" "$https_origin$image_path" \
    -o "$test_root/product-image.png"
tr -d '\r' < "$test_root/product-image.headers" | grep -Eqi '^Content-Type: image/png'
cmp "$test_root/expected-product-image.png" "$test_root/product-image.png"
code="$(curl "${curl_options[@]}" --cacert "$test_root/tls/cert.pem" \
    -X POST --data-binary 'must-not-reach-nas' -o "$test_root/product-image-post" \
    -w '%{http_code}' "$https_origin$image_path")"
test "$code" = 403
curl "${curl_options[@]}" --cacert "$test_root/tls/cert.pem" --fail \
    "$https_origin/index.html" -o "$test_root/https-index.html"
for path in /rpa/v1/product-images-not-public/sample.png /rpa/v1/products/sample; do
    curl "${curl_options[@]}" --cacert "$test_root/tls/cert.pem" --fail \
        "$https_origin$path" -o "$test_root/non-image-rpa.html"
    cmp "$test_root/https-index.html" "$test_root/non-image-rpa.html"
done
printf 'PASS: production inner and host TLS Nginx preserve multipart bytes through 10 MiB; over-12 MiB bodies return 413 without forwarding (transport fixture only)\n'
printf 'PASS: exact internal mobile v1 prefix returns backend JSON; URI/body/auth preserved, missing/invalid auth stays 401, adjacent prefixes stay frontend\n'
printf 'PASS: application Session path reaches the backend only through host TLS and overwrites a spoofed proto (transport fixture only)\n'
printf 'PASS: ProductDataCenter image GET/HEAD uses the exact public HTTPS prefix; writes are denied and adjacent RPA paths stay frontend\n'
printf 'PASS: authenticated precheck signing streams at both proxies, preserves path/headers and never logs request bodies\n'
