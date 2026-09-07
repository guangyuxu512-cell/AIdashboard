#!/usr/bin/env bash

# Shared, non-evaluating reader for the root-managed production .env file.
# Deployment callers must not source that file: secrets may contain shell
# metacharacters and it is not executable configuration.
production_environment_file=""

production_env_open() {
    local environment_file="$1"
    if [[ ! -f "$environment_file" ]]; then
        echo "Production environment file is missing" >&2
        return 1
    fi
    production_environment_file="$environment_file"
}

production_env_read() {
    local key="$1"
    local line=""
    line="$(grep -m1 -E "^${key}=" "$production_environment_file" || true)"
    if [[ -z "$line" ]]; then
        return 1
    fi
    local value="${line#*=}"
    if [[ "$value" =~ ^\".*\"$ || "$value" =~ ^\'.*\'$ ]]; then
        value="${value:1:${#value}-2}"
    fi
    printf '%s' "$value"
}

production_env_load_required() {
    local key="$1"
    local value=""
    if ! value="$(production_env_read "$key")" || [[ -z "$value" ]]; then
        echo "Production environment is missing $key" >&2
        return 1
    fi
    printf -v "$key" '%s' "$value"
}
