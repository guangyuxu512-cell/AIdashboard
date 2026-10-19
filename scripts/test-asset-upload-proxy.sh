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

# Use the production image/template and the same bounded writable mounts as Compose.
# Only this container publishes ports, both on randomly allocated host loopback ports.
frontend="$(docker run -d --name "$run_id-frontend" --read-only \
    -p 127.0.0.1::18080 -p 127.0.0.1::443 \
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
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer

class Receiver(BaseHTTPRequestHandler):
    arrivals = 0

    def reply(self, status, text):
        body = (text + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.reply(200, str(Receiver.arrivals))

    def do_POST(self):
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
    "$frontend_image" \
    '${PRODUCTION_DOMAIN} ${PRODUCTION_ACME_WEBROOT_DIR} ${PRODUCTION_TLS_CERTIFICATE_PATH} ${PRODUCTION_TLS_CERTIFICATE_KEY_PATH} ${BACKEND_BIND_PORT} ${FRONTEND_BIND_PORT}' \
    < "$repository_root/deploy/production/host-nginx.conf.template" > "$test_root/host.conf"
host="$(docker run -d --name "$run_id-host" --read-only \
    --network "container:$frontend" --entrypoint nginx \
    --tmpfs /var/cache/nginx:size=16m,mode=1777 \
    --tmpfs /var/run:size=1m,mode=1777 --tmpfs /tmp:size=16m,mode=1777 \
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
done
printf 'PASS: production inner and host TLS Nginx preserve multipart bytes through 10 MiB; over-12 MiB bodies return 413 without forwarding (transport fixture only)\n'
