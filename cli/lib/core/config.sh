#!/usr/bin/env bash
# lib/core/config.sh - Configuration management

# Guard against multiple sourcing
[[ -n "${CONFIG_LOADED:-}" ]] && return 0
readonly CONFIG_LOADED=1

# Export REPO_ROOT for config expansions
export REPO_ROOT="$(get_repo_root)"

# Configuration file locations
PROJECT_CONFIG="$REPO_ROOT/config.toml"
USER_CONFIG="$REPO_ROOT/.erenshor/config.local.toml"

# Default configuration values
# NOTE: Variant-specific paths (game, unity, database) should NOT be here.
# They are dynamically resolved via variant_get_path() in variants.sh
declare -gA CONFIG=(
    [default_variant]="main"

    [steam.app_id]="2382520"
    [steam.username]=""
    [steam.platform]="windows"

    [paths.wiki_project]="/Users/joaichberger/Projects/erenshor-wiki"

    [unity.version]="2021.3.45f1"
    [unity.path]="/Applications/Unity/Hub/Editor/2021.3.45f1/Unity.app/Contents/MacOS/Unity"
    [unity.timeout]="3600"

    [assetripper.path]="$HOME/Projects/AssetRipper/AssetRipper.GUI.Free"
    [assetripper.port]="8080"
    [assetripper.timeout]="3600"

    [export.entities]="all"
    [export.log_level]="normal"

    [database.backup_count]="10"
    [database.validate]="true"

    [notifications.enabled]="false"
    [notifications.email]=""
    [notifications.on_success]="true"
    [notifications.on_failure]="true"

    [behavior.confirm_destructive]="true"
    [behavior.parallel_downloads]="true"
    [behavior.max_retries]="3"
    [behavior.retry_delay]="30"

    [logging.level]="info"
    [logging.file_enabled]="true"
    [logging.console_enabled]="true"
)

# Load single configuration file
_config_load_file() {
    local config_file="$1"

    if [[ ! -f "$config_file" ]]; then
        # Config doesn't exist, skip
        return 0
    fi

    # Simple TOML parser (handles basic key = "value" format)
    local section=""
    while IFS= read -r line; do
        # Remove carriage returns (for cross-platform compatibility)
        line="${line//$'\r'/}"

        # Remove comments and trim whitespace
        line=$(echo "$line" | sed 's/#.*//' | xargs)

        # Skip empty lines
        [[ -z "$line" ]] && continue

        # Section header
        if [[ "$line" =~ ^\[([^]]+)\]$ ]]; then
            section="${BASH_REMATCH[1]}"
            continue
        fi

        # Key-value pair
        if [[ "$line" =~ ^([^=]+)=(.+)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"

            # Trim whitespace
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)

            # Remove quotes
            value="${value#\"}"
            value="${value%\"}"
            value="${value#\'}"
            value="${value%\'}"

            # Expand environment variables safely (without eval)
            # Only expand $REPO_ROOT, $HOME, and tilde
            if [[ "$value" == *'$'* ]] || [[ "$value" == '~'* ]]; then
                value="${value//\$REPO_ROOT/$REPO_ROOT}"
                value="${value//\$HOME/$HOME}"
                value="${value/#\~/$HOME}"
            fi

            # Store with section prefix
            if [[ -n "$section" ]]; then
                CONFIG["$section.$key"]="$value"
            else
                CONFIG["$key"]="$value"
            fi
        fi
    done < "$config_file"
}

# Load configuration (loads both project and user configs with proper precedence)
config_load() {
    # Load project config first (base settings)
    if [[ -f "$PROJECT_CONFIG" ]]; then
        _config_load_file "$PROJECT_CONFIG"
    fi

    # Load user config second (overrides)
    if [[ -f "$USER_CONFIG" ]]; then
        _config_load_file "$USER_CONFIG"
    fi
}

# Get configuration value
config_get() {
    local key="$1"
    local default="${2:-}"

    local value=""

    # Try with global. prefix first (from config.toml)
    if [[ "$key" != global.* ]]; then
        value="${CONFIG["global.$key"]:-}"
    fi

    # Fall back to direct key (hardcoded defaults)
    if [[ -z "$value" ]]; then
        value="${CONFIG[$key]:-}"
    fi

    # Fall back to default parameter
    if [[ -z "$value" ]]; then
        value="$default"
    fi

    # Safe expansion - only expand $REPO_ROOT and $HOME
    value="${value//\$REPO_ROOT/$REPO_ROOT}"
    value="${value//\$HOME/$HOME}"
    value="${value/#\~/$HOME}"
    echo "$value"
}

# Get variant-specific config with fallback to global
config_get_variant() {
    local variant="$1"
    local key="$2"
    local default="${3:-}"

    # Try variant-specific first: variants.main.unity_project
    local variant_value="${CONFIG["variants.$variant.$key"]:-}"
    if [[ -n "$variant_value" ]]; then
        # Safe expansion - only expand $REPO_ROOT and $HOME
        variant_value="${variant_value//\$REPO_ROOT/$REPO_ROOT}"
        variant_value="${variant_value//\$HOME/$HOME}"
        variant_value="${variant_value/#\~/$HOME}"
        echo "$variant_value"
        return 0
    fi

    # Try global: global.unity.path
    local global_value="${CONFIG["global.$key"]:-}"
    if [[ -n "$global_value" ]]; then
        # Safe expansion - only expand $REPO_ROOT and $HOME
        global_value="${global_value//\$REPO_ROOT/$REPO_ROOT}"
        global_value="${global_value//\$HOME/$HOME}"
        global_value="${global_value/#\~/$HOME}"
        echo "$global_value"
        return 0
    fi

    # Fall back to non-prefixed key
    local plain_value="${CONFIG[$key]:-$default}"
    # Safe expansion - only expand $REPO_ROOT and $HOME
    plain_value="${plain_value//\$REPO_ROOT/$REPO_ROOT}"
    plain_value="${plain_value//\$HOME/$HOME}"
    plain_value="${plain_value/#\~/$HOME}"
    echo "$plain_value"
}

# Set configuration value (in memory only)
config_set() {
    local key="$1"
    local value="$2"

    CONFIG["$key"]="$value"
}

# Helper function to escape and quote values properly for TOML
_config_quote_value() {
    local val="$1"
    # If value contains spaces or special characters, quote it
    if [[ "$val" =~ [[:space:]] ]] || [[ "$val" == *"\$"* ]]; then
        echo "\"$val\""
    # If it's already a boolean or number, leave unquoted
    elif [[ "$val" =~ ^(true|false|[0-9]+)$ ]]; then
        echo "$val"
    # If empty, use empty quotes
    elif [[ -z "$val" ]]; then
        echo '""'
    # Otherwise, quote it
    else
        echo "\"$val\""
    fi
}

# Helper to get config value with fallback
_config_get_with_default() {
    local key="$1"
    local default="$2"
    echo "${CONFIG[$key]:-$default}"
}

# Save configuration to file
config_save() {
    local config_file="${1:-$USER_CONFIG}"
    local config_dir=$(dirname "$config_file")

    mkdir -p "$config_dir"

    # Write config file with actual CONFIG values
    cat > "$config_file" << EOF
# Erenshor Data Mining Pipeline Configuration
version = "1.0"

[steam]
# Steam configuration for game downloads
app_id = $(_config_quote_value "$(_config_get_with_default steam.app_id "2382520")")
username = $(_config_quote_value "$(_config_get_with_default steam.username "")")           # Leave empty to be prompted
platform = $(_config_quote_value "$(_config_get_with_default steam.platform "windows")")    # Force Windows version download

[paths]
# Project paths (variant-specific paths should use variants.{variant}.* config instead)
wiki_project = $(_config_quote_value "$(_config_get_with_default paths.wiki_project "\$REPO_ROOT/../erenshor-wiki")")

[unity]
# Unity configuration
version = $(_config_quote_value "$(_config_get_with_default unity.version "2021.3.45f1")")
path = $(_config_quote_value "$(_config_get_with_default unity.path "/Applications/Unity/Hub/Editor/2021.3.45f1/Unity.app/Contents/MacOS/Unity")")
timeout = $(_config_get_with_default unity.timeout 3600)          # 60 minutes max for export

[assetripper]
# AssetRipper configuration
path = $(_config_quote_value "$(_config_get_with_default assetripper.path "\$HOME/Projects/AssetRipper/AssetRipper.GUI.Free")")
port = $(_config_get_with_default assetripper.port 8080)             # Web API port
timeout = $(_config_get_with_default assetripper.timeout 3600)          # 60 minutes max for extraction

[export]
# Export configuration
entities = $(_config_quote_value "$(_config_get_with_default export.entities "all")")        # Entity types to export (or comma-separated list)
log_level = $(_config_quote_value "$(_config_get_with_default export.log_level "normal")")    # quiet, normal, verbose

[database]
# Database configuration
backup_count = $(_config_get_with_default database.backup_count 10)       # Keep last N backups
validate = $(_config_get_with_default database.validate true)         # Validate after export/deploy

[notifications]
# Notification configuration
enabled = $(_config_get_with_default notifications.enabled false)
email = $(_config_quote_value "$(_config_get_with_default notifications.email "")")              # Email for notifications
on_success = $(_config_get_with_default notifications.on_success true)
on_failure = $(_config_get_with_default notifications.on_failure true)

[behavior]
# Behavioral settings
confirm_destructive = $(_config_get_with_default behavior.confirm_destructive true)      # Confirm destructive operations
parallel_downloads = $(_config_get_with_default behavior.parallel_downloads true)       # Enable parallel operations
max_retries = $(_config_get_with_default behavior.max_retries 3)                 # Retry failed operations
retry_delay = $(_config_get_with_default behavior.retry_delay 30)                # Seconds between retries

[logging]
# Logging configuration
level = $(_config_quote_value "$(_config_get_with_default logging.level "info")")                  # debug, info, warn, error
file_enabled = $(_config_get_with_default logging.file_enabled true)
console_enabled = $(_config_get_with_default logging.console_enabled true)
EOF
}

# Validate configuration
config_validate() {
    local errors=0

    # Check Unity path
    local unity_path=$(config_get unity.path)
    if [[ ! -x "$unity_path" ]]; then
        log_error "Unity not found at: $unity_path"
        ((errors++))
    fi

    # Check project paths exist
    local unity_project=$(config_get paths.unity_project)
    if [[ ! -d "$unity_project" ]]; then
        log_error "Unity project not found: $unity_project"
        ((errors++))
    fi

    local wiki_project=$(config_get paths.wiki_project)
    if [[ ! -d "$wiki_project" ]]; then
        log_warn "Wiki project not found: $wiki_project"
    fi

    return $errors
}

# Get all config keys for a section
config_keys() {
    local section="$1"
    local prefix="$section."

    for key in "${!CONFIG[@]}"; do
        if [[ "$key" == "$prefix"* ]]; then
            echo "${key#$prefix}"
        fi
    done
}

# Print configuration (for debugging)
config_print() {
    local section="${1:-}"

    if [[ -n "$section" ]]; then
        for key in $(config_keys "$section"); do
            echo "$section.$key = $(config_get "$section.$key")"
        done
    else
        for key in "${!CONFIG[@]}"; do
            echo "$key = ${CONFIG[$key]}"
        done
    fi
}
