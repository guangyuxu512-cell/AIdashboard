#!/usr/bin/env bash
set -euo pipefail
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$repository_root/deploy/production/pc-static-assets.sh"
test_root="$(mktemp -d)"
trap 'rm -rf -- "$test_root"' EXIT
store="$test_root/store"
a=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
b=bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
c=cccccccccccccccccccccccccccccccccccccccc
d=dddddddddddddddddddddddddddddddddddddddd
mkdir -p "$test_root/a" "$test_root/b" "$test_root/c" "$test_root/d"
printf 'old chunk' > "$test_root/a/old-12345678.js"
printf 'old style' > "$test_root/a/old-12345678.css"
printf 'font' > "$test_root/a/font-12345678.woff2"
printf 'image' > "$test_root/a/image-12345678.webp"
printf 'shared' > "$test_root/a/shared-12345678.js"
printf 'never exported' > "$test_root/a/index.html"
printf 'never exported' > "$test_root/a/.env"
printf 'never exported' > "$test_root/a/source-12345678.js.map"
ln -s "$test_root/a/index.html" "$test_root/a/link-12345678.js"
if [[ ! -L "$test_root/a/link-12345678.js" ]]; then
    # Git Bash may implement ln as a copy; Linux CI covers actual symlinks.
    rm "$test_root/a/link-12345678.js"
    printf 'SKIP: native symlink test unavailable on this host\n'
fi
printf 'Vue dependency' > "$test_root/a/AssetDownloadStatusBar.vue_vue_type_style_index_0_scoped_ef246b8a_lang-DBAvGTgy.js"
printf 'new chunk' > "$test_root/b/new-12345678.js"
cp "$test_root/a/shared-12345678.js" "$test_root/b/"
printf 'third chunk' > "$test_root/c/third-12345678.js"
printf 'failed chunk' > "$test_root/d/failed-12345678.js"

pc_assets_import "$store" "$a" "$test_root/a"
pc_assets_activate "$store" "$a" '' 1000
test "$(find "$store/public" -type f | wc -l)" -eq 6
cmp "$test_root/a/old-12345678.js" "$store/public/assets/old-12345678.js"
pc_assets_import "$store" "$b" "$test_root/b"
pc_assets_activate "$store" "$b" "$a" 2000
test "$(cat "$store/releases/$a/retired-at")" = 2000
# Repeated successful deployments do not restart an already retired timer.
pc_assets_activate "$store" "$b" "$a" 3000
test "$(cat "$store/releases/$a/retired-at")" = 2000
# Current and rollback survive even when older than seven days.
pc_assets_activate "$store" "$b" "$a" 700000
test -f "$store/public/assets/old-12345678.js"
# Failed candidate extraction does not mutate retirement/prune the active set.
pc_assets_import "$store" "$d" "$test_root/d"
test ! -f "$store/releases/$d/retired-at"
test "$(cat "$store/releases/$a/retired-at")" = 2000
test -f "$store/public/assets/old-12345678.js"
pc_assets_import "$store" "$c" "$test_root/c"
pc_assets_activate "$store" "$c" "$b" 700001
test ! -e "$store/releases/$a"
test ! -f "$store/public/assets/old-12345678.js"
test -f "$store/public/assets/shared-12345678.js"
test "$(cat "$store/releases/$b/retired-at")" = 700001
# Reactivating a retained release starts a new service lifetime.
pc_assets_activate "$store" "$b" "$c" 700002
test ! -f "$store/releases/$b/retired-at"
test -f "$store/public/assets/third-12345678.js"
printf 'collision' > "$test_root/c/shared-12345678.js"
if pc_assets_import "$store" "$c" "$test_root/c" 2>/dev/null; then
    echo 'Expected collision rejection' >&2; exit 1
fi
printf 'PASS: static asset filtering, byte integrity, seven-day retirement, shared hashes, current/rollback protection and failed candidate preservation\n'
