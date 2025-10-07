#!/usr/bin/env bash
# lib/core/logger.sh - Logging system

# Guard against multiple sourcing
[[ -n "${LOGGER_LOADED:-}" ]] && return 0
readonly LOGGER_LOADED=1

# Get script directory
LOGGER_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$LOGGER_SCRIPT_DIR/../ui/colors.sh"
source "$LOGGER_SCRIPT_DIR/utils.sh"

# Log levels
readonly LOG_LEVEL_DEBUG=0
readonly LOG_LEVEL_INFO=1
readonly LOG_LEVEL_WARN=2
readonly LOG_LEVEL_ERROR=3

# Global log configuration
LOG_LEVEL=${LOG_LEVEL:-$LOG_LEVEL_INFO}
LOG_FILE="${LOG_FILE:-}"
LOG_MODULE="${LOG_MODULE:-main}"
LOG_TO_CONSOLE=${LOG_TO_CONSOLE:-true}
LOG_TO_FILE=${LOG_TO_FILE:-true}

# Initialize logging
log_init() {
    # Get repo root for default log directory
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local repo_root="$(cd "$script_dir/../../.." && pwd)"

    # Default to project-local logs
    local log_dir="${1:-$repo_root/.erenshor/logs}"
    local log_name="${2:-erenshor.log}"

    mkdir -p "$log_dir"
    LOG_FILE="$log_dir/$log_name"

    # Create operation-specific log
    local operation_log_dir="$log_dir/operations"
    mkdir -p "$operation_log_dir"

    local timestamp=$(timestamp_file)
    local operation_log="$operation_log_dir/${LOG_MODULE}_${timestamp}.log"

    # Also log to operation-specific file
    export OPERATION_LOG="$operation_log"

    # Write log header
    {
        echo "==========================================="
        echo "Erenshor Data Mining Pipeline"
        echo "Started: $(timestamp)"
        echo "Module: $LOG_MODULE"
        echo "Log Level: $LOG_LEVEL"
        echo "==========================================="
        echo ""
    } >> "$LOG_FILE"

    # Same header to operation log
    cat "$LOG_FILE" > "$operation_log"
}

# Internal log function
_log() {
    local level=$1
    local level_name=$2
    local color=$3
    local module=$4
    shift 4
    local message="$*"

    # Check if we should log this level
    if [[ $level -lt $LOG_LEVEL ]]; then
        return
    fi

    local timestamp=$(timestamp)
    local log_line="[$timestamp] [$level_name] [$module] $message"

    # Write to files
    if [[ "$LOG_TO_FILE" == true && -n "$LOG_FILE" ]]; then
        echo "$log_line" >> "$LOG_FILE"
        if [[ -n "${OPERATION_LOG:-}" ]]; then
            echo "$log_line" >> "$OPERATION_LOG"
        fi
    fi

    # Write to console with color
    if [[ "$LOG_TO_CONSOLE" == true ]]; then
        echo -e "${color}${log_line}${COLOR_RESET}"
    fi
}

# Public logging functions
log_debug() {
    _log $LOG_LEVEL_DEBUG "DEBUG" "$COLOR_DIM" "$LOG_MODULE" "$@"
}

log_info() {
    _log $LOG_LEVEL_INFO "INFO" "$COLOR_CYAN" "$LOG_MODULE" "$@"
}

log_warn() {
    _log $LOG_LEVEL_WARN "WARN" "$COLOR_YELLOW" "$LOG_MODULE" "$@"
}

log_error() {
    _log $LOG_LEVEL_ERROR "ERROR" "$COLOR_RED" "$LOG_MODULE" "$@"
}

# Set log level from string
log_set_level() {
    local level_str="${1,,}"  # Convert to lowercase

    case "$level_str" in
        debug)
            LOG_LEVEL=$LOG_LEVEL_DEBUG
            ;;
        info)
            LOG_LEVEL=$LOG_LEVEL_INFO
            ;;
        warn|warning)
            LOG_LEVEL=$LOG_LEVEL_WARN
            ;;
        error)
            LOG_LEVEL=$LOG_LEVEL_ERROR
            ;;
        quiet)
            LOG_LEVEL=$LOG_LEVEL_ERROR
            LOG_TO_CONSOLE=false
            ;;
        *)
            log_warn "Unknown log level: $level_str (using INFO)"
            LOG_LEVEL=$LOG_LEVEL_INFO
            ;;
    esac
}

# Get latest log file for module
log_get_latest() {
    local module="${1:-$LOG_MODULE}"
    local log_dir="${LOG_FILE%/*}"
    local operation_dir="$log_dir/operations"

    if [[ -d "$operation_dir" ]]; then
        ls -t "$operation_dir/${module}_"*.log 2>/dev/null | head -1
    fi
}

# Rotate logs if they get too large
log_rotate() {
    local max_size_mb=${1:-10}

    if [[ ! -f "$LOG_FILE" ]]; then
        return
    fi

    local size_mb=$(du -m "$LOG_FILE" | cut -f1)

    if [[ $size_mb -gt $max_size_mb ]]; then
        local backup="${LOG_FILE}.1"
        mv "$LOG_FILE" "$backup"
        gzip "$backup" 2>/dev/null || true
        log_debug "Rotated log file (${size_mb}MB > ${max_size_mb}MB)"
    fi
}
