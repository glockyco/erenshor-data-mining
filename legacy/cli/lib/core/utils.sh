#!/usr/bin/env bash
# lib/core/utils.sh - Common utility functions

# Guard against multiple sourcing
[[ -n "${UTILS_LOADED:-}" ]] && return 0
readonly UTILS_LOADED=1

# Resolve path to absolute
resolve_path() {
    local path="$1"

    # Handle tilde expansion
    path="${path/#\~/$HOME}"

    # Convert to absolute path
    if [[ "$path" != /* ]]; then
        path="$(pwd)/$path"
    fi

    # Normalize path (requires realpath)
    realpath "$path" 2>/dev/null || echo "$path"
}

# Check if command exists
command_exists() {
    command -v "$1" &>/dev/null
}

# Get current timestamp
timestamp() {
    date +"%Y-%m-%d %H:%M:%S"
}

# Get ISO timestamp
timestamp_iso() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

# Get timestamp for filenames
timestamp_file() {
    date +"%Y%m%d_%H%M%S"
}

# Get file size in human-readable format
file_size() {
    local path="$1"
    if [[ -f "$path" ]]; then
        if [[ "$(uname)" == "Darwin" ]]; then
            stat -f%z "$path" | numfmt --to=iec-i 2>/dev/null || du -h "$path" | cut -f1
        else
            stat -c%s "$path" | numfmt --to=iec-i 2>/dev/null || du -h "$path" | cut -f1
        fi
    else
        echo "0B"
    fi
}

# Check disk space (returns MB available)
disk_space_available() {
    local path="${1:-.}"
    df -m "$path" | awk 'NR==2 {print $4}'
}

# Check if enough disk space is available
check_disk_space() {
    local required_mb=$1
    local path="${2:-.}"
    local available=$(disk_space_available "$path")

    if [[ $available -lt $required_mb ]]; then
        return 1
    fi
    return 0
}

# Wait with timeout for a process
wait_with_timeout() {
    local timeout=$1
    local pid=$2
    local elapsed=0

    while kill -0 "$pid" 2>/dev/null; do
        if [[ $elapsed -ge $timeout ]]; then
            return 1
        fi
        sleep 1
        ((elapsed++))
    done

    wait "$pid"
    return $?
}

# Retry command with exponential backoff
retry() {
    local max_attempts=$1
    local delay=$2
    shift 2
    local cmd=("$@")

    local attempt=1
    while [[ $attempt -le $max_attempts ]]; do
        if "${cmd[@]}"; then
            return 0
        fi

        if [[ $attempt -lt $max_attempts ]]; then
            sleep "$delay"
            delay=$((delay * 2))  # Exponential backoff
        fi

        ((attempt++))
    done

    return 1
}

# Calculate duration between two timestamps
duration() {
    local start=$1
    local end=$2
    local diff=$((end - start))

    local hours=$((diff / 3600))
    local mins=$(( (diff % 3600) / 60 ))
    local secs=$((diff % 60))

    if [[ $hours -gt 0 ]]; then
        printf "%dh %dm %ds" "$hours" "$mins" "$secs"
    elif [[ $mins -gt 0 ]]; then
        printf "%dm %ds" "$mins" "$secs"
    else
        printf "%ds" "$secs"
    fi
}

# Get SQLite database stats
db_stats() {
    local db_path="$1"

    if [[ ! -f "$db_path" ]]; then
        echo "Database not found"
        return 1
    fi

    sqlite3 "$db_path" << 'EOF'
.mode list
SELECT 'Items', COUNT(*) FROM Items
UNION ALL SELECT 'Characters', COUNT(*) FROM Characters
UNION ALL SELECT 'Quests', COUNT(*) FROM Quests
UNION ALL SELECT 'Spells', COUNT(*) FROM Spells
UNION ALL SELECT 'Skills', COUNT(*) FROM Skills;
EOF
}

# Verify SQLite database integrity
verify_database() {
    local db_path="$1"

    if [[ ! -f "$db_path" ]]; then
        return 1
    fi

    # Check if valid SQLite database
    if ! sqlite3 "$db_path" "PRAGMA integrity_check;" &>/dev/null; then
        return 1
    fi

    # Check if Items table exists
    if ! sqlite3 "$db_path" "SELECT COUNT(*) FROM Items LIMIT 1;" &>/dev/null; then
        return 1
    fi

    return 0
}

# Get repository root directory
# Walks up the directory tree looking for repository marker files
get_repo_root() {
    # Use cached value if available
    if [[ -n "${REPO_ROOT:-}" ]]; then
        echo "$REPO_ROOT"
        return 0
    fi

    local dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Walk up the directory tree looking for repository markers
    while [[ "$dir" != "/" ]]; do
        # Check for repository marker files
        if [[ -f "$dir/pyproject.toml" ]] || \
           [[ -f "$dir/config.toml" ]] || \
           [[ -d "$dir/.git" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done

    # Not found
    echo "ERROR: Repository root not found" >&2
    return 1
}
