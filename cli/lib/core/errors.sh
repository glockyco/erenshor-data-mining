#!/usr/bin/env bash
# lib/core/errors.sh - Error handling and exit codes

# Guard against multiple sourcing
[[ -n "${ERRORS_LOADED:-}" ]] && return 0
readonly ERRORS_LOADED=1

# Error codes
readonly ERROR_SUCCESS=0
readonly ERROR_GENERAL=1
readonly ERROR_ARGS=2
readonly ERROR_CONFIG=10
readonly ERROR_DEPENDENCY=11
readonly ERROR_NETWORK=12
readonly ERROR_PERMISSION=13
readonly ERROR_DISK=14
readonly ERROR_PROCESS=15
readonly ERROR_VALIDATION=16
readonly ERROR_USER_CANCEL=17
readonly ERROR_NOT_FOUND=18
readonly ERROR_TIMEOUT=19
readonly ERROR_UNKNOWN=99

# Error messages
declare -A ERROR_MESSAGES=(
    [$ERROR_SUCCESS]="Success"
    [$ERROR_GENERAL]="General error"
    [$ERROR_ARGS]="Invalid arguments"
    [$ERROR_CONFIG]="Configuration error"
    [$ERROR_DEPENDENCY]="Missing dependency"
    [$ERROR_NETWORK]="Network error"
    [$ERROR_PERMISSION]="Permission denied"
    [$ERROR_DISK]="Disk space or I/O error"
    [$ERROR_PROCESS]="External process failed"
    [$ERROR_VALIDATION]="Validation failed"
    [$ERROR_USER_CANCEL]="Operation cancelled by user"
    [$ERROR_NOT_FOUND]="File or resource not found"
    [$ERROR_TIMEOUT]="Operation timed out"
    [$ERROR_UNKNOWN]="Unknown error"
)

# Get error message for code
error_message() {
    local code=$1
    echo "${ERROR_MESSAGES[$code]:-Unknown error ($code)}"
}

# Exit with error code and message
die() {
    local code=$1
    shift
    local message="$*"

    if [[ -z "$message" ]]; then
        message=$(error_message "$code")
    fi

    error "$message"
    exit "$code"
}

# Check dependency and exit if missing
require_command() {
    local cmd=$1
    local install_hint="${2:-}"

    if ! command_exists "$cmd"; then
        error "Required command not found: $cmd"
        if [[ -n "$install_hint" ]]; then
            echo ""
            echo "Install with: $install_hint"
        fi
        exit $ERROR_DEPENDENCY
    fi
}

# Check file exists and exit if not
require_file() {
    local file=$1
    local message="${2:-File not found: $file}"

    if [[ ! -f "$file" ]]; then
        die $ERROR_NOT_FOUND "$message"
    fi
}

# Check directory exists and exit if not
require_directory() {
    local dir=$1
    local message="${2:-Directory not found: $dir}"

    if [[ ! -d "$dir" ]]; then
        die $ERROR_NOT_FOUND "$message"
    fi
}

# Check disk space and exit if insufficient
require_disk_space() {
    local required_mb=$1
    local path="${2:-.}"

    if ! check_disk_space "$required_mb" "$path"; then
        local available=$(disk_space_available "$path")
        die $ERROR_DISK "Insufficient disk space. Required: ${required_mb}MB, Available: ${available}MB"
    fi
}

# Trap errors and cleanup
setup_error_trap() {
    local cleanup_function="${1:-cleanup}"

    trap "error 'Script interrupted'; $cleanup_function; exit $ERROR_USER_CANCEL" INT TERM
    trap "error 'Script failed'; $cleanup_function; exit $ERROR_GENERAL" ERR
}

# Default cleanup function
cleanup() {
    # Override this in your scripts
    :
}
