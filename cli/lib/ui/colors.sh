#!/usr/bin/env bash
# lib/ui/colors.sh - Terminal colors and formatting

# Guard against multiple sourcing
[[ -n "${COLORS_LOADED:-}" ]] && return 0
readonly COLORS_LOADED=1

# Check if output is to a terminal
is_tty() {
    [[ -t 1 ]]
}

# Color codes (only if terminal)
if is_tty; then
    readonly COLOR_RESET='\033[0m'
    readonly COLOR_BOLD='\033[1m'
    readonly COLOR_DIM='\033[2m'

    readonly COLOR_BLACK='\033[0;30m'
    readonly COLOR_RED='\033[0;31m'
    readonly COLOR_GREEN='\033[0;32m'
    readonly COLOR_YELLOW='\033[0;33m'
    readonly COLOR_BLUE='\033[0;34m'
    readonly COLOR_MAGENTA='\033[0;35m'
    readonly COLOR_CYAN='\033[0;36m'
    readonly COLOR_WHITE='\033[0;37m'

    # Symbols/Emojis
    readonly SYMBOL_CHECK='✓'
    readonly SYMBOL_CROSS='✗'
    readonly SYMBOL_WARN='⚠'
    readonly SYMBOL_INFO='ℹ'
    readonly SYMBOL_ROCKET='▶'
    readonly SYMBOL_CLOCK='⏳'
    readonly SYMBOL_SPARKLE='✨'
else
    readonly COLOR_RESET=''
    readonly COLOR_BOLD=''
    readonly COLOR_DIM=''
    readonly COLOR_BLACK=''
    readonly COLOR_RED=''
    readonly COLOR_GREEN=''
    readonly COLOR_YELLOW=''
    readonly COLOR_BLUE=''
    readonly COLOR_MAGENTA=''
    readonly COLOR_CYAN=''
    readonly COLOR_WHITE=''

    readonly SYMBOL_CHECK='[OK]'
    readonly SYMBOL_CROSS='[ERROR]'
    readonly SYMBOL_WARN='[WARN]'
    readonly SYMBOL_INFO='[INFO]'
    readonly SYMBOL_ROCKET='>'
    readonly SYMBOL_CLOCK='[...]'
    readonly SYMBOL_SPARKLE='[*]'
fi

# Formatting functions
color_echo() {
    local color="$1"
    shift
    echo -e "${color}$*${COLOR_RESET}"
}

bold() {
    echo -e "${COLOR_BOLD}$*${COLOR_RESET}"
}

dim() {
    echo -e "${COLOR_DIM}$*${COLOR_RESET}"
}

# Semantic colors
success() {
    color_echo "$COLOR_GREEN" "$SYMBOL_CHECK $*"
}

error() {
    color_echo "$COLOR_RED" "$SYMBOL_CROSS $*" >&2
}

warning() {
    color_echo "$COLOR_YELLOW" "$SYMBOL_WARN $*"
}

info() {
    color_echo "$COLOR_CYAN" "$SYMBOL_INFO $*"
}

step() {
    color_echo "$COLOR_BLUE" "$SYMBOL_ROCKET $*"
}

waiting() {
    color_echo "$COLOR_YELLOW" "$SYMBOL_CLOCK $*"
}

celebrate() {
    color_echo "$COLOR_MAGENTA" "$SYMBOL_SPARKLE $*"
}
