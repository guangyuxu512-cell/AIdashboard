#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
workflow_path="$repository_root/.github/workflows/production-deploy.yml"
tls_workflow_path="$repository_root/.github/workflows/production-provision-ip-tls.yml"

required_fragments=(
    '  workflow_dispatch:'
    '      backup_reference:'
    '  actions: read'
    $'      - uses: actions/checkout@v4\n        with:\n          ref: main\n          fetch-depth: 0'
    "cancel-in-progress: false"
    '        shell: pwsh'
    '          GH_TOKEN: ${{ github.token }}'
    './scripts/deploy-production.ps1 -DeploySha $env:DEPLOY_SHA'
    '-PublicHost $env:PRODUCTION_DEPLOY_HOST -Mode Deploy'
    '-BackupReference $env:BACKUP_REFERENCE'
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

# Every application deployment is explicit. Neither a completed CI nor a push
# may silently start the old, competing GitHub CD path.
! grep -Eq '^  (workflow_run|push|schedule):' "$workflow_path"
! grep -Eq '^ *scp |^ *ssh ' "$workflow_path"
assert_keepalive_transport_contract "$tls_workflow_path" 1 3 1

grep -Fq 'status=\$?; rm -rf --' "$tls_workflow_path"
grep -Fq 'exit \$status' "$tls_workflow_path"
grep -Fq "'StrictHostKeyChecking=yes'" "$repository_root/scripts/deploy-production.ps1"
grep -Fq "'ServerAliveInterval=30'" "$repository_root/scripts/deploy-production.ps1"
grep -Fq "'ServerAliveCountMax=3'" "$repository_root/scripts/deploy-production.ps1"
grep -Fq 'flock -n 9' "$repository_root/scripts/remote-deploy-production.sh"
grep -Fq 'verify-active-release.sh' "$repository_root/scripts/deploy-production.ps1"
grep -Fq 'mobile/public/manifest.webmanifest' "$repository_root/scripts/remote-deploy-production.sh"
grep -Fq 'verify_mobile_frontend' "$repository_root/scripts/remote-deploy-production.sh"
grep -Fq 'absolute_redirect off;' "$repository_root/frontend/deploy/default.conf.template"
grep -Fq '308 with the proxy-safe relative Location /mobile/' "$repository_root/scripts/remote-deploy-production.sh"
grep -Fq "^Location: /mobile/\$" "$repository_root/.github/workflows/ci.yml"

echo 'Local production CD, explicit emergency entry and SSH keepalive regressions passed'
