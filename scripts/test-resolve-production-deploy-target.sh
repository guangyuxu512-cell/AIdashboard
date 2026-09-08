#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
resolver="$repository_root/scripts/resolve-production-deploy-target.sh"
test_root="$(mktemp -d)"

cleanup() {
    rm -rf -- "$test_root"
}
trap cleanup EXIT

origin="$test_root/origin.git"
seed="$test_root/seed"
worktree="$test_root/worktree"
advance="$test_root/advance"

git init --bare "$origin" >/dev/null
git clone "$origin" "$seed" >/dev/null
git -C "$seed" config user.name 'production deploy target test'
git -C "$seed" config user.email 'production-deploy-target-test@example.invalid'
printf 'first\n' > "$seed/release.txt"
git -C "$seed" add release.txt
git -C "$seed" commit -m 'first release' >/dev/null
git -C "$seed" branch -M main
git -C "$seed" push origin main >/dev/null
first_sha="$(git -C "$seed" rev-parse HEAD)"

git clone "$origin" "$worktree" >/dev/null
git -C "$worktree" checkout main >/dev/null

run_resolver() {
    local event_name="$1"
    local manual_sha="$2"
    local ci_sha="$3"
    local output="$4"
    (
        cd "$worktree"
        GITHUB_OUTPUT="$output" bash "$resolver" "$event_name" "$manual_sha" "$ci_sha"
    )
}

manual_output="$test_root/manual.out"
run_resolver workflow_dispatch "$first_sha" '' "$manual_output"
grep -Fqx 'should_deploy=true' "$manual_output"
grep -Fqx "deploy_sha=$first_sha" "$manual_output"

auto_output="$test_root/auto.out"
run_resolver workflow_run '' "$first_sha" "$auto_output"
grep -Fqx 'should_deploy=true' "$auto_output"
grep -Fqx "deploy_sha=$first_sha" "$auto_output"

git clone "$origin" "$advance" >/dev/null
git -C "$advance" checkout main >/dev/null
git -C "$advance" config user.name 'production deploy target test'
git -C "$advance" config user.email 'production-deploy-target-test@example.invalid'
printf 'second\n' >> "$advance/release.txt"
git -C "$advance" add release.txt
git -C "$advance" commit -m 'second release' >/dev/null
git -C "$advance" push origin main >/dev/null
second_sha="$(git -C "$advance" rev-parse HEAD)"

stale_output="$test_root/stale.out"
run_resolver workflow_run '' "$first_sha" "$stale_output"
grep -Fqx 'should_deploy=false' "$stale_output"
grep -Fqx "deploy_sha=$first_sha" "$stale_output"

manual_stale_output="$test_root/manual-stale.out"
set +e
run_resolver workflow_dispatch "$first_sha" '' "$manual_stale_output" >"$test_root/manual-stale.stderr" 2>&1
manual_stale_status=$?
set -e
[[ "$manual_stale_status" -eq 2 ]]
grep -Fqx 'Manual production deployment SHA must equal the current origin/main commit' "$test_root/manual-stale.stderr"

latest_output="$test_root/latest.out"
run_resolver workflow_run '' "$second_sha" "$latest_output"
grep -Fqx 'should_deploy=true' "$latest_output"
grep -Fqx "deploy_sha=$second_sha" "$latest_output"

echo 'Production deployment target resolution regression passed'
