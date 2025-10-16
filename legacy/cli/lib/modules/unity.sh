#!/usr/bin/env bash
# lib/modules/unity.sh - Unity export operations

# Guard against multiple sourcing
[[ -n "${UNITY_MODULE_LOADED:-}" ]] && return 0
readonly UNITY_MODULE_LOADED=1

# Module initialization
UNITY_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$UNITY_MODULE_DIR/../core/logger.sh"
source "$UNITY_MODULE_DIR/../core/errors.sh"
source "$UNITY_MODULE_DIR/../core/config.sh"

# Check if Unity is installed
unity_check_installed() {
    local unity_path=$(config_get unity.path)

    if [[ ! -x "$unity_path" ]]; then
        log_error "Unity not found at: $unity_path"
        return $ERROR_DEPENDENCY
    fi

    return 0
}

# Verify Unity export script exists
# Usage: unity_verify_export_script
unity_verify_export_script() {
    local repo_root="${REPO_ROOT:-$(get_repo_root)}"
    local export_script="$repo_root/src/export.sh"

    # Check if source script exists and is executable
    if [[ ! -f "$export_script" ]]; then
        log_error "Export script not found: $export_script"
        return $ERROR_NOT_FOUND
    fi

    if [[ ! -x "$export_script" ]]; then
        log_debug "Making export script executable"
        chmod +x "$export_script" || {
            log_error "Failed to make export script executable"
            return $ERROR_PROCESS
        }
    fi

    log_debug "Export script ready: $export_script"
    return 0
}

# Export game data using Unity batch mode
# Usage: unity_export [unity_project] [output_db] [entities] [variant]
unity_export() {
    local unity_project="${1:-$(config_get paths.unity_project)}"
    local output_db="${2:-$(config_get paths.output)/erenshor.sqlite}"
    local entities="${3:-all}"
    local variant="${4:-}"

    log_info "Starting Unity export..."
    log_debug "Unity project: $unity_project"
    log_debug "Output database: $output_db"
    log_debug "Entities: $entities"
    log_debug "Variant: ${variant:-default}"

    # Check Unity installation
    if ! unity_check_installed; then
        return $ERROR_DEPENDENCY
    fi

    local unity_path=$(config_get unity.path)
    local timeout=$(config_get unity.timeout)

    # Verify Unity project
    require_directory "$unity_project" "Unity project not found: $unity_project"

    # Verify export script exists
    if ! unity_verify_export_script; then
        log_error "Failed to verify export script"
        return $ERROR_DEPENDENCY
    fi

    # Create output directory
    mkdir -p "$(dirname "$output_db")"

    # Determine log directory (variant-specific if provided, otherwise global)
    local logs_dir
    if [[ -n "$variant" ]]; then
        logs_dir=$(config_get_variant "$variant" "logs" "$REPO_ROOT/variants/$variant/logs")
    else
        logs_dir=$(config_get "paths.logs" "$REPO_ROOT/.erenshor/logs")
    fi

    local log_file="$logs_dir/unity_export_$(timestamp_file).log"
    mkdir -p "$(dirname "$log_file")"

    # Use export.sh script
    local repo_root="${REPO_ROOT:-$(get_repo_root)}"
    local export_script="$repo_root/src/export.sh"

    log_info "Using export script: $export_script"

    local cmd=(
        "$export_script"
        "$unity_project"
        "-o" "$output_db"
        "-l" "normal"
    )

    if [[ "$entities" != "all" ]]; then
        cmd+=("-e" "$entities")
    fi

    log_debug "Executing: ${cmd[*]}"

    if timeout "$timeout" "${cmd[@]}" 2>&1 | tee "$log_file"; then
        log_info "Unity export complete"
        log_info "Database: $output_db"
        return 0
    else
        local exit_code=$?
        log_error "Unity export failed with exit code: $exit_code"
        log_error "Check log: $log_file"
        return $ERROR_PROCESS
    fi
}

# Get Unity version
unity_get_version() {
    local unity_path=$(config_get unity.path)

    if [[ ! -x "$unity_path" ]]; then
        echo "unknown"
        return
    fi

    # Unity version is in the path
    if [[ "$unity_path" =~ ([0-9]+\.[0-9]+\.[0-9]+[a-z][0-9]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo "unknown"
    fi
}

# Validate Unity project
unity_validate_project() {
    local unity_project="${1:-$(config_get paths.unity_project)}"

    # Check for essential directories
    if [[ ! -d "$unity_project/Assets" ]]; then
        log_error "Assets directory not found in Unity project"
        return 1
    fi

    if [[ ! -d "$unity_project/ProjectSettings" ]]; then
        log_error "ProjectSettings directory not found in Unity project"
        return 1
    fi

    # Check for Editor scripts (in src/)
    local repo_root="$(cd "$unity_project/../.." && pwd)"
    if [[ ! -d "$repo_root/src/Assets/Editor" ]]; then
        log_warn "Editor scripts directory not found"
    fi

    return 0
}
