#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workflow_path="$repository_root/.github/workflows/production-deploy.yml"
tls_workflow_path="$repository_root/.github/workflows/production-provision-ip-tls.yml"

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
    "backend frontend mobile deploy/production"
)

for fragment in "${required_fragments[@]}"; do
    if ! grep -Fq -- "$fragment" "$workflow_path"; then
        echo "Missing production deployment workflow contract: $fragment" >&2
        exit 1
    fi
done

keepalive_options='ssh_options=(-o StrictHostKeyChecking=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3)'

assert_keepalive_transport_contract() {
    local workflow_path="$1"
    local expected_option_blocks="$2"
    local expected_transports="$3"
    local expected_fail_fast_blocks="$4"
    local option_blocks transports fail_fast_blocks

    option_blocks="$(grep -Fc -- "$keepalive_options" "$workflow_path" || true)"
    transports="$(grep -Ec '(ssh|scp) "\$\{ssh_options\[@\]\}"' "$workflow_path" || true)"
    fail_fast_blocks="$(grep -Fc -- 'set -euo pipefail' "$workflow_path" || true)"

    test "$option_blocks" = "$expected_option_blocks"
    test "$transports" = "$expected_transports"
    test "$fail_fast_blocks" = "$expected_fail_fast_blocks"
}

assert_keepalive_transport_contract "$workflow_path" 2 5 2
assert_keepalive_transport_contract "$tls_workflow_path" 1 3 1

grep -Fq 'status=\$?; rm -f --' "$workflow_path"
grep -Fq 'status=\$?; rm -rf --' "$tls_workflow_path"
grep -Fq 'exit \$status' "$workflow_path"
grep -Fq 'exit \$status' "$tls_workflow_path"
grep -Fq 'mobile/public/manifest.webmanifest' "$repository_root/scripts/remote-deploy-production.sh"
grep -Fq 'verify_mobile_frontend' "$repository_root/scripts/remote-deploy-production.sh"

echo 'Production deployment workflow trigger and SSH keepalive regressions passed'
