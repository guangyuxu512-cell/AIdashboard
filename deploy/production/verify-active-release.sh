#!/usr/bin/env bash
set -euo pipefail

release_sha="${1:?release SHA is required}"
if [[ ! "$release_sha" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Active release verification requires a full lowercase SHA" >&2
    exit 2
fi

# Caller holds .deploy.lock. A current symlink alone is not deployment proof:
# compose up may have been interrupted after current was switched.
for service in douyin-signer backend frontend; do
    container="control-center-$service-prod"
    expected_image="ecommerce-control-center-$service-prod:$release_sha"
    if ! observed="$(docker inspect --format '{{.Config.Image}}|{{.State.Running}}|{{.State.Paused}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container" 2>/dev/null)"; then
        echo "Active release container is unavailable: $container" >&2
        exit 1
    fi
    IFS='|' read -r image running paused health <<< "$observed"
    if [[ "$image" != "$expected_image" || "$running" != "true" || "$paused" != "false" ]]; then
        echo "Active release container SHA or running state does not match: $container" >&2
        exit 1
    fi
    if [[ "$service" != "frontend" && "$health" != "healthy" ]]; then
        echo "Active release container is not healthy: $container" >&2
        exit 1
    fi
done
