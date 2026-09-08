#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workflow_path="$repository_root/.github/workflows/production-deploy.yml"

required_fragments=(
    $'  workflow_run:\n    workflows: [CI]\n    branches: [main]\n    types: [completed]'
    "github.event.workflow_run.conclusion == 'success'"
    "github.event.workflow_run.event == 'push'"
    "github.event.workflow_run.head_branch == 'main'"
    'CI_DEPLOY_SHA: ${{ github.event.workflow_run.head_sha }}'
    "steps.deploy_target.outputs.should_deploy == 'true'"
    "steps.active_release.outputs.already_deployed != 'true'"
    "cancel-in-progress: false"
    "bash scripts/resolve-production-deploy-target.sh"
)

for fragment in "${required_fragments[@]}"; do
    if ! grep -Fq -- "$fragment" "$workflow_path"; then
        echo "Missing production deployment workflow contract: $fragment" >&2
        exit 1
    fi
done

echo 'Production deployment workflow trigger contract regression passed'
