#!/usr/bin/env bash
# Sourced by the release script. Only PC content-hashed build assets live here.
# Metadata/index.html/API data never enter the public directory.

pc_assets_import() (
    set -euo pipefail
    local store="$1" sha="$2" source="$3" file relative destination
    [[ "$store" == /* && "$sha" =~ ^[0-9a-f]{40}$ && -d "$source" ]]
    install -d -m 0755 "$store/releases/$sha/assets" "$store/public/assets"
    while IFS= read -r -d '' file; do
        relative="${file#"$source/"}"
        # Vite-generated hashed JS/CSS and their font/image dependencies only.
        # Exclude sourcemaps, HTML, dotfiles, symlinks and arbitrary runtime data.
        [[ "$relative" =~ ^([A-Za-z0-9_-]+/)*[^./][^/]*-[A-Za-z0-9_-]{8,}\.(js|mjs|css|woff2?|ttf|otf|png|jpe?g|gif|svg|webp|avif|ico)$ ]] || continue
        destination="$store/public/assets/$relative"
        if [[ -f "$destination" ]] && ! cmp -s -- "$file" "$destination"; then
            echo "PC asset name collision: $relative" >&2
            exit 1
        fi
        install -D -m 0644 "$file" "$store/releases/$sha/assets/$relative"
        if [[ ! -f "$destination" ]]; then
            install -d -m 0755 "$(dirname "$destination")"
            # Rename only complete files into the live public directory.
            local temporary
            temporary="$(mktemp "$store/.asset-XXXXXX")"
            install -m 0644 "$file" "$temporary"
            mv -- "$temporary" "$destination"
        fi
    done < <(find "$source" -type f -print0)
    if [[ -z "$(find "$store/releases/$sha/assets" -type f -name '*.js' -print -quit)" ]]; then
        echo "Release $sha has no retained PC JavaScript assets" >&2
        exit 1
    fi
)

pc_assets_capture_image() (
    set -euo pipefail
    local store="$1" sha="$2" image="$3" temporary container=""
    temporary="$(mktemp -d)"
    trap 'if [[ -n "$container" ]]; then docker rm "$container" >/dev/null; fi; rm -rf -- "$temporary"' EXIT
    # Never start the export container or read its env/logs.
    container="$(docker create "$image")"
    docker cp "$container:/usr/share/nginx/html/assets/." "$temporary/"
    pc_assets_import "$store" "$sha" "$temporary"
)

pc_assets_activate() (
    set -euo pipefail
    local store="$1" current="$2" previous="${3:-}" now="${4:-$(date +%s)}"
    local release sha retired file relative needed other
    [[ "$store" == /* && "$current" =~ ^[0-9a-f]{40}$ ]]
    [[ -z "$previous" || "$previous" =~ ^[0-9a-f]{40}$ ]]
    [[ "$now" =~ ^[0-9]+$ && -d "$store/releases/$current/assets" ]]
    for release in "$store"/releases/*; do
        [[ -d "$release" && ! -L "$release" ]] || continue
        sha="$(basename "$release")"
        [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || continue
        if [[ "$sha" == "$current" ]]; then
            rm -f -- "$release/retired-at"
            continue
        fi
        if [[ ! -f "$release/retired-at" ]]; then
            printf '%s\n' "$now" > "$release/retired-at"
        fi
        retired="$(<"$release/retired-at")"
        [[ "$retired" =~ ^[0-9]+$ ]] || return 1
        # The immediate rollback release is protected regardless of its age.
        if [[ "$sha" != "$previous" && $((now - retired)) -ge 604800 ]]; then
            rm -rf -- "$release"
        fi
    done
    # A hash shared with another retained release must remain available.
    while IFS= read -r -d '' file; do
        relative="${file#"$store/public/assets/"}"
        needed=false
        for other in "$store"/releases/*/assets; do
            if [[ -f "$other/$relative" ]]; then needed=true; break; fi
        done
        if [[ "$needed" == false ]]; then rm -- "$file"; fi
    done < <(find "$store/public/assets" -type f -print0)
)
