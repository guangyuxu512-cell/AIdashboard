#!/usr/bin/env bash
set -euo pipefail

event_name="${1:?GitHub event name is required}"
manual_deploy_sha="${2:-}"
ci_deploy_sha="${3:-}"
output_file="${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"

case "$event_name" in
    workflow_dispatch)
        deploy_sha="$manual_deploy_sha"
        ;;
    workflow_run)
        deploy_sha="$ci_deploy_sha"
        ;;
    *)
        echo "Unsupported production deployment event: $event_name" >&2
        exit 2
        ;;
esac

if [[ ! "$deploy_sha" =~ ^[0-9a-f]{40}$ ]]; then
    echo "Production deployment requires a full lowercase Git commit SHA" >&2
    exit 2
fi

git fetch --no-tags origin +refs/heads/main:refs/remotes/origin/main
published_main_sha="$(git rev-parse origin/main)"

if [[ "$deploy_sha" != "$published_main_sha" ]]; then
    if [[ "$event_name" == "workflow_run" ]]; then
        printf 'should_deploy=false\n' >> "$output_file"
        printf 'deploy_sha=%s\n' "$deploy_sha" >> "$output_file"
        echo "Skipping stale CI-verified production deployment target: $deploy_sha" >&2
        exit 0
    fi

    echo "Manual production deployment SHA must equal the current origin/main commit" >&2
    exit 2
fi

git cat-file -e "$deploy_sha^{commit}"
printf 'should_deploy=true\n' >> "$output_file"
printf 'deploy_sha=%s\n' "$deploy_sha" >> "$output_file"
