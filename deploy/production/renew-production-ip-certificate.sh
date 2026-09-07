#!/usr/bin/env bash
set -euo pipefail

remote_root="${1:?production deployment root is required}"
if [[ "$remote_root" != "/opt/ecommerce-control-center/production" ]]; then
    echo "Refusing an unexpected production deployment root" >&2
    exit 2
fi

source "$remote_root/acme/production-env.sh"
production_env_open "$remote_root/.env"
for key in PRODUCTION_ACME_STATE_DIR PRODUCTION_ACME_WEBROOT_DIR PRODUCTION_ACME_CERTBOT_IMAGE; do
    production_env_load_required "$key"
done

hooks_directory="$remote_root/acme/hooks"
docker run --rm --network host \
    -e ACME_WEBROOT=/var/www/control-center-acme \
    -v "$PRODUCTION_ACME_STATE_DIR:/etc/letsencrypt" \
    -v "$PRODUCTION_ACME_WEBROOT_DIR:/var/www/control-center-acme" \
    -v "$hooks_directory:/opt/control-center-acme:ro" \
    "$PRODUCTION_ACME_CERTBOT_IMAGE" renew --non-interactive

nginx -s reload
