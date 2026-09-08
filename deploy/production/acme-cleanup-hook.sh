#!/bin/sh
set -eu

: "${ACME_WEBROOT:?ACME_WEBROOT is required}"
: "${CERTBOT_TOKEN:?CERTBOT_TOKEN is required}"

rm -f -- "$ACME_WEBROOT/.well-known/acme-challenge/$CERTBOT_TOKEN"
