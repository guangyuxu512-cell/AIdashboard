#!/bin/sh
set -eu

: "${ACME_WEBROOT:?ACME_WEBROOT is required}"
: "${CERTBOT_TOKEN:?CERTBOT_TOKEN is required}"
: "${CERTBOT_VALIDATION:?CERTBOT_VALIDATION is required}"

challenge_directory="$ACME_WEBROOT/.well-known/acme-challenge"
mkdir -p "$challenge_directory"
chmod 0755 "$challenge_directory"
printf '%s' "$CERTBOT_VALIDATION" > "$challenge_directory/$CERTBOT_TOKEN"
