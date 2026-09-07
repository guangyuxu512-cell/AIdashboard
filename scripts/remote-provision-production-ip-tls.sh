#!/usr/bin/env bash
set -euo pipefail

remote_root="${1:?production deployment root is required}"
if [[ "$remote_root" != "/opt/ecommerce-control-center/production" ]]; then
    echo "Refusing an unexpected production deployment root" >&2
    exit 2
fi

script_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repository_directory="$(cd "$script_directory/.." && pwd)"
source "$script_directory/production-env.sh"
production_env_open "$remote_root/.env"

for key in \
    PRODUCTION_DOMAIN \
    PRODUCTION_ACME_EMAIL \
    PRODUCTION_ACME_CERT_NAME \
    PRODUCTION_ACME_CERTBOT_IMAGE \
    PRODUCTION_ACME_STATE_DIR \
    PRODUCTION_ACME_WEBROOT_DIR \
    PRODUCTION_TLS_CERTIFICATE_PATH \
    PRODUCTION_TLS_CERTIFICATE_KEY_PATH \
    PRODUCTION_NGINX_VHOST_DIR; do
    production_env_load_required "$key"
done

if ! python3 - "$PRODUCTION_DOMAIN" <<'PY'
import ipaddress
import sys

address = ipaddress.ip_address(sys.argv[1])
raise SystemExit(0 if address.version == 4 and address.is_global else 1)
PY
then
    echo "PRODUCTION_DOMAIN must be a public IPv4 address for IP-certificate issuance" >&2
    exit 2
fi
if [[ ! "$PRODUCTION_ACME_CERT_NAME" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "PRODUCTION_ACME_CERT_NAME contains unsupported path characters" >&2
    exit 2
fi
if [[ ! -d "$PRODUCTION_NGINX_VHOST_DIR" ]]; then
    echo "Configured production Nginx vhost directory is unavailable" >&2
    exit 2
fi
for command in docker envsubst install nginx openssl python3 systemctl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Production host is missing required command: $command" >&2
        exit 2
    fi
done

acme_root="$remote_root/acme"
hooks_directory="$acme_root/hooks"
renew_script="$acme_root/renew.sh"
nginx_target="$PRODUCTION_NGINX_VHOST_DIR/control-center-production.conf"
bootstrap_template="$repository_directory/deploy/production/host-nginx-http-acme.conf.template"
bootstrap_config="$acme_root/control-center-production-http-acme.conf"
tls_bootstrap_template="$repository_directory/deploy/production/host-nginx-ip-tls-bootstrap.conf.template"
tls_bootstrap_config="$acme_root/control-center-production-ip-tls-bootstrap.conf"
nginx_backup="$acme_root/control-center-production.conf.before-ip-tls"
existing_vhost=false
provision_succeeded=false

restore_previous_vhost() {
    if [[ "$existing_vhost" == "true" ]]; then
        install -m 0644 "$nginx_backup" "$nginx_target"
    else
        rm -f -- "$nginx_target"
    fi
    nginx -t >/dev/null 2>&1 && nginx -s reload >/dev/null 2>&1 || true
}

cleanup_on_failure() {
    if [[ "$provision_succeeded" != "true" ]]; then
        restore_previous_vhost
    fi
}
trap cleanup_on_failure EXIT

install -d -m 0700 "$acme_root" "$hooks_directory" "$PRODUCTION_ACME_STATE_DIR"
install -d -m 0755 "$PRODUCTION_ACME_WEBROOT_DIR"
install -m 0700 "$repository_directory/deploy/production/acme-auth-hook.sh" "$hooks_directory/auth.sh"
install -m 0700 "$repository_directory/deploy/production/acme-cleanup-hook.sh" "$hooks_directory/cleanup.sh"
install -m 0700 "$repository_directory/deploy/production/renew-production-ip-certificate.sh" "$renew_script"
install -m 0600 "$script_directory/production-env.sh" "$acme_root/production-env.sh"

if [[ -f "$nginx_target" ]]; then
    install -m 0600 "$nginx_target" "$nginx_backup"
    existing_vhost=true
fi

if [[ ! -f "$PRODUCTION_TLS_CERTIFICATE_PATH" || ! -f "$PRODUCTION_TLS_CERTIFICATE_KEY_PATH" ]]; then
    export PRODUCTION_DOMAIN PRODUCTION_ACME_WEBROOT_DIR
    envsubst '$PRODUCTION_DOMAIN $PRODUCTION_ACME_WEBROOT_DIR' \
        < "$bootstrap_template" \
        > "$bootstrap_config"
    install -m 0644 "$bootstrap_config" "$nginx_target"
    nginx -t
    nginx -s reload

    docker run --rm --network host \
        -e ACME_WEBROOT=/var/www/control-center-acme \
        -v "$PRODUCTION_ACME_STATE_DIR:/etc/letsencrypt" \
        -v "$PRODUCTION_ACME_WEBROOT_DIR:/var/www/control-center-acme" \
        -v "$hooks_directory:/opt/control-center-acme:ro" \
        "$PRODUCTION_ACME_CERTBOT_IMAGE" certonly \
        --manual \
        --non-interactive \
        --agree-tos \
        --no-eff-email \
        --email "$PRODUCTION_ACME_EMAIL" \
        --preferred-profile shortlived \
        --preferred-challenges http \
        --manual-auth-hook /opt/control-center-acme/auth.sh \
        --manual-cleanup-hook /opt/control-center-acme/cleanup.sh \
        --ip-address "$PRODUCTION_DOMAIN" \
        --cert-name "$PRODUCTION_ACME_CERT_NAME"
fi

if [[ ! -f "$PRODUCTION_TLS_CERTIFICATE_PATH" || ! -f "$PRODUCTION_TLS_CERTIFICATE_KEY_PATH" ]]; then
    echo "IP certificate files were not created at the configured paths" >&2
    exit 1
fi
openssl x509 -in "$PRODUCTION_TLS_CERTIFICATE_PATH" -noout -ext subjectAltName | grep -F "IP Address:$PRODUCTION_DOMAIN" >/dev/null

# Before the application release is deployed, expose only a TLS-valid 503 vhost.
# This proves that the certificate is presented for the public IP without making
# the application available before its own deployment health checks complete.
export PRODUCTION_DOMAIN PRODUCTION_ACME_WEBROOT_DIR PRODUCTION_TLS_CERTIFICATE_PATH PRODUCTION_TLS_CERTIFICATE_KEY_PATH
envsubst '$PRODUCTION_DOMAIN $PRODUCTION_ACME_WEBROOT_DIR $PRODUCTION_TLS_CERTIFICATE_PATH $PRODUCTION_TLS_CERTIFICATE_KEY_PATH' \
    < "$tls_bootstrap_template" \
    > "$tls_bootstrap_config"
install -m 0644 "$tls_bootstrap_config" "$nginx_target"
nginx -t
nginx -s reload

install -m 0644 "$repository_directory/deploy/production/control-center-production-ip-acme-renew.service.template" \
    /etc/systemd/system/control-center-production-ip-acme-renew.service
install -m 0644 "$repository_directory/deploy/production/control-center-production-ip-acme-renew.timer.template" \
    /etc/systemd/system/control-center-production-ip-acme-renew.timer
systemctl daemon-reload
systemctl enable --now control-center-production-ip-acme-renew.timer
systemctl is-enabled --quiet control-center-production-ip-acme-renew.timer
systemctl is-active --quiet control-center-production-ip-acme-renew.timer

provision_succeeded=true
echo "Production public-IP TLS certificate is provisioned and renewal timer is active"
