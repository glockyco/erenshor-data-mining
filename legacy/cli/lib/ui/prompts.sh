#!/usr/bin/env bash
# lib/ui/prompts.sh - Interactive prompts

# Get script directory
PROMPTS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROMPTS_SCRIPT_DIR/colors.sh"

# Confirm prompt (Y/n)
confirm() {
    local message="$1"
    local default="${2:-y}"

    local prompt
    if [[ "$default" == "y" ]]; then
        prompt="[Y/n]"
    else
        prompt="[y/N]"
    fi

    echo -n "$message $prompt: "
    read -r response

    # If empty, use default
    if [[ -z "$response" ]]; then
        response="$default"
    fi

    # Convert to lowercase
    response=$(echo "$response" | tr '[:upper:]' '[:lower:]')

    [[ "$response" == "y" || "$response" == "yes" ]]
}

# Prompt for input with default
prompt() {
    local message="$1"
    local default="$2"
    local secure="${3:-false}"

    if [[ -n "$default" ]]; then
        echo -n "$message [$default]: "
    else
        echo -n "$message: "
    fi

    if [[ "$secure" == true ]]; then
        read -rs response
        echo ""  # New line after hidden input
    else
        read -r response
    fi

    # If empty, use default
    if [[ -z "$response" ]]; then
        response="$default"
    fi

    echo "$response"
}

# Prompt for password (hidden input)
prompt_password() {
    local message="$1"

    echo -n "$message: "
    read -rs password
    echo ""  # New line after password

    echo "$password"
}

# Select from options
select_option() {
    local prompt="$1"
    shift
    local options=("$@")

    echo "$prompt"
    echo ""

    local i=1
    for option in "${options[@]}"; do
        echo "  $i) $option"
        ((i++))
    done

    echo ""
    echo -n "Select [1-${#options[@]}]: "
    read -r selection

    # Validate selection
    if [[ ! "$selection" =~ ^[0-9]+$ ]] || [[ $selection -lt 1 ]] || [[ $selection -gt ${#options[@]} ]]; then
        error "Invalid selection"
        return 1
    fi

    # Return selected option (0-indexed)
    echo "${options[$((selection-1))]}"
}

# Wait for user to press any key
press_any_key() {
    local message="${1:-Press any key to continue...}"

    echo ""
    echo -n "$message"
    read -n 1 -s
    echo ""
}
