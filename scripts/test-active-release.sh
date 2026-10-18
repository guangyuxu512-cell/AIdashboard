#!/usr/bin/env bash
set -euo pipefail

repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test_root="$(mktemp -d)"
trap 'rm -rf -- "$test_root"' EXIT
mkdir "$test_root/bin"
cat > "$test_root/bin/docker" <<'EOF'
#!/usr/bin/env bash
[[ "$1" == inspect ]] || exit 99
container="${@: -1}"
service="${container#control-center-}"
service="${service%-prod}"
image="ecommerce-control-center-$service-prod:$TEST_ACTIVE_SHA"
running=true paused=false health=healthy
[[ "$service" != frontend ]] || health=none
if [[ "$container" == "${TEST_BAD_CONTAINER:-}" ]]; then
    case "$TEST_BAD_STATE" in
        missing) exit 1 ;;
        wrong_sha) image="ecommerce-control-center-$service-prod:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" ;;
        stopped) running=false ;;
        paused) paused=true ;;
        unhealthy|starting|none) health="$TEST_BAD_STATE" ;;
        *) exit 98 ;;
    esac
fi
printf '%s\n' "$container" >> "$TEST_INSPECT_LOG"
printf '%s|%s|%s|%s\n' "$image" "$running" "$paused" "$health"
EOF
chmod 0700 "$test_root/bin/docker"
export TEST_ACTIVE_SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export TEST_INSPECT_LOG="$test_root/inspect.log"
checker="$repository_root/deploy/production/verify-active-release.sh"
PATH="$test_root/bin:$PATH" bash "$checker" "$TEST_ACTIVE_SHA" > "$test_root/good.out"
[[ ! -s "$test_root/good.out" && "$(wc -l < "$TEST_INSPECT_LOG")" -eq 3 ]]

cases=1
for service in douyin-signer backend frontend; do
    states=(missing wrong_sha stopped paused)
    if [[ "$service" != frontend ]]; then states+=(unhealthy starting none); fi
    for state in "${states[@]}"; do
        set +e
        TEST_BAD_CONTAINER="control-center-$service-prod" TEST_BAD_STATE="$state" PATH="$test_root/bin:$PATH" \
            bash "$checker" "$TEST_ACTIVE_SHA" > "$test_root/bad.out" 2>&1
        status=$?
        set -e
        [[ "$status" -eq 1 ]]
        cases=$((cases + 1))
    done
done
echo "Active release runtime regressions passed ($cases cases; Docker inspect is simulated)."
