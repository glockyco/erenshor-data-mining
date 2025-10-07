#!/usr/bin/env bash
# lib/ui/progress.sh - Progress indicators

# Get script directory
PROGRESS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROGRESS_SCRIPT_DIR/colors.sh"

# Progress bar
progress_bar() {
    local current=$1
    local total=$2
    local width=${3:-40}
    local prefix=${4:-"Progress"}

    if [[ $total -eq 0 ]]; then
        return
    fi

    local percent=$((current * 100 / total))
    local filled=$((current * width / total))
    local empty=$((width - filled))

    printf "\r%s: [" "$prefix"
    printf "%${filled}s" | tr ' ' '━'
    printf "%${empty}s" | tr ' ' ' '
    printf "] %3d%%" "$percent"

    if [[ $current -eq $total ]]; then
        echo ""  # New line when complete
    fi
}

# Spinner (for indefinite operations)
spinner_start() {
    local message=${1:-"Working"}
    local spinstr='⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏'
    local delay=0.1

    (
        while true; do
            for (( i=0; i<${#spinstr}; i++ )); do
                printf "\r%s %s" "${spinstr:$i:1}" "$message"
                sleep $delay
            done
        done
    ) &

    export SPINNER_PID=$!
}

# Stop spinner
spinner_stop() {
    if [[ -n "${SPINNER_PID:-}" ]]; then
        kill "$SPINNER_PID" 2>/dev/null || true
        wait "$SPINNER_PID" 2>/dev/null || true
        unset SPINNER_PID
        printf "\r%s\n" "$(success "Done")"
    fi
}

# Progress message with step number
step_progress() {
    local current=$1
    local total=$2
    local message="$3"

    echo ""
    step "Step $current/$total: $message"
}

# Show download progress
download_progress() {
    local current_mb=$1
    local total_mb=$2
    local speed_mbs=$3

    local percent=$((current_mb * 100 / total_mb))
    local remaining_mb=$((total_mb - current_mb))
    local eta_seconds=$((remaining_mb / speed_mbs))

    local eta_mins=$((eta_seconds / 60))
    local eta_secs=$((eta_seconds % 60))

    printf "\r  Progress: %d%% (%.1f MB / %.1f MB) | Speed: %.1f MB/s | ETA: %dm %ds" \
        "$percent" "$current_mb" "$total_mb" "$speed_mbs" "$eta_mins" "$eta_secs"

    if [[ $current_mb -ge $total_mb ]]; then
        echo ""
    fi
}
