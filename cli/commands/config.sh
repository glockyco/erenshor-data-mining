#!/usr/bin/env bash
# commands/config.sh - Configuration management

command_main() {
    local action="${1:-show}"

    case "$action" in
        show|list)
            config_show
            ;;
        set)
            config_set_value "${2:-}" "${3:-}"
            ;;
        get)
            config_get_value "${2:-}"
            ;;
        create)
            config_create
            ;;
        edit)
            config_edit
            ;;
        *)
            show_config_help
            ;;
    esac
}

config_show() {
    echo ""
    bold "=== Erenshor Configuration ==="
    echo ""

    if [[ ! -f "$USER_CONFIG" ]]; then
        warning "Config file not found: $USER_CONFIG"
        echo ""
        echo "Create with: erenshor config create"
        return
    fi

    success "Config file: $USER_CONFIG"
    echo ""

    # Show key sections
    for section in steam paths unity assetripper export database behavior logging; do
        echo "$(bold "[$section]")"
        config_keys "$section" | while read -r key; do
            local value=$(config_get "$section.$key")
            echo "  $key = $value"
        done
        echo ""
    done
}

config_get_value() {
    local key="$1"

    if [[ -z "$key" ]]; then
        error "Key required"
        echo "Usage: erenshor config get <key>"
        exit 1
    fi

    local value=$(config_get "$key")
    echo "$value"
}

config_set_value() {
    local key="$1"
    local value="$2"

    if [[ -z "$key" ]]; then
        error "Key required"
        echo "Usage: erenshor config set <key> <value>"
        exit 1
    fi

    # Check if value was provided (even if empty)
    # Note: We can't easily distinguish between "" and no arg in bash,
    # so we just check if key is present
    if [[ $# -lt 2 ]]; then
        error "Value required"
        echo "Usage: erenshor config set <key> <value>"
        echo "Note: To set empty value, use: erenshor config set <key> \"\""
        exit 1
    fi

    # Load current config
    config_load

    # Set new value in memory (allow empty strings)
    config_set "$key" "$value"

    # Save to file
    config_save

    success "Set $key = $value"
}

config_create() {
    if [[ -f "$USER_CONFIG" ]]; then
        if ! confirm "Config file already exists. Overwrite?"; then
            info "Cancelled"
            exit 0
        fi
    fi

    config_save
    success "Created config file: $USER_CONFIG"
}

config_edit() {
    if [[ ! -f "$USER_CONFIG" ]]; then
        if confirm "Config file doesn't exist. Create it?"; then
            config_save
        else
            exit 0
        fi
    fi

    local editor="${EDITOR:-nano}"
    "$editor" "$USER_CONFIG"
}

show_config_help() {
    cat << 'EOF'
erenshor config - Manage configuration

USAGE:
    erenshor config [action] [args]

ACTIONS:
    show              Show current configuration (default)
    get <key>         Get a configuration value
    set <key> <value> Set a configuration value
    create            Create default configuration file
    edit              Edit configuration file

EXAMPLES:
    # Show all configuration
    erenshor config

    # Get a value
    erenshor config get unity.path

    # Set a value
    erenshor config set steam.username myuser

    # Create default config
    erenshor config create

    # Edit config in editor
    erenshor config edit

CONFIGURATION FILE:
    Location: ~/.erenshor/config.toml
    Format: TOML (simple key=value pairs in sections)

SEE ALSO:
    erenshor status     Show system status
    erenshor doctor     Diagnose configuration issues
EOF
}
