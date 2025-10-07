#!/usr/bin/env bash
# commands/check.sh - Check for game updates

# Command entry point
command_main() {
    local show_details=false
    local variant="$(config_get default_variant)"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--details)
                show_details=true
                shift
                ;;
            --variant)
                variant="$2"
                shift 2
                ;;
            -h|--help)
                show_check_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor check --help' for usage."
                exit 1
                ;;
        esac
    done

    # Validate variant
    if ! variant_validate "$variant"; then
        die $ERROR_ARGS "Invalid variant: $variant"
    fi

    # Set module name for logging
    export LOG_MODULE="check"

    # Show header
    echo ""
    info "Checking for game updates ($(variant_get_display_name "$variant"))..."
    echo ""

    # Get variant-specific paths
    local game_path=$(variant_get_path "$variant" "game")

    # Check if game is installed
    local current_build=$(steamcmd_get_current_build "$game_path")

    if [[ "$current_build" == "0" ]]; then
        warning "Game not downloaded yet"
        echo ""
        info "To download: $(bold "erenshor download --variant $variant")"
        exit 0
    fi

    # Show current build
    if [[ "$current_build" == "manual" ]]; then
        info "Current build: Manual download (manifest incomplete)"
    else
        info "Current build: $current_build"
    fi

    if [[ "$show_details" == true ]]; then
        local game_size=$(steamcmd_get_game_size "$game_path")

        echo ""
        info "Installation details:"
        echo "  Location: $game_path"
        echo "  Size: ${game_size}MB"
    fi

    echo ""
    info "To update: $(bold "erenshor update --variant $variant")"
    echo ""
}

# Show help
show_check_help() {
    cat << 'EOF'
erenshor check - Check for game updates

USAGE:
    erenshor check [OPTIONS]

DESCRIPTION:
    Checks if the game has been downloaded and shows the current build ID.
    Does not download or modify anything.

OPTIONS:
    -d, --details         Show installation details
    --variant VARIANT     Check specific variant (main, playtest, demo)
    -h, --help            Show this help message

EXAMPLES:
    # Check for updates (default variant: main)
    erenshor check

    # Show detailed information
    erenshor check --details

    # Check specific variant
    erenshor check --variant playtest

SEE ALSO:
    erenshor update     Run full update pipeline
    erenshor status     Show system status
    erenshor download   Download game files
EOF
}
