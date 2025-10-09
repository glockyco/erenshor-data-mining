#!/usr/bin/env bash
# commands/extract.sh - Extract assets with AssetRipper

# Command entry point
command_main() {
    local force=false
    local variant="$(config_get default_variant)"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                force=true
                shift
                ;;
            --variant)
                variant="$2"
                shift 2
                ;;
            -h|--help)
                show_extract_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor extract --help' for usage."
                exit 1
                ;;
        esac
    done

    # Validate variant
    if ! variant_validate "$variant"; then
        die $ERROR_ARGS "Invalid variant: $variant"
    fi

    # Set module name for logging
    export LOG_MODULE="extract"

    # Start timer
    local start_time=$(date +%s)

    # Show header
    echo ""
    celebrate "Extracting Game Assets ($(variant_get_display_name "$variant"))"
    echo ""

    # Get variant-specific paths
    local game_path=$(variant_get_path "$variant" "game")
    local unity_path=$(variant_get_path "$variant" "unity")

    # Initialize variant if needed
    if ! variant_exists "$variant"; then
        variant_init "$variant"
    fi

    # Check if game is downloaded
    local current_build=$(steamcmd_get_current_build "$game_path")

    if [[ "$current_build" == "0" ]]; then
        error "Game not downloaded yet"
        echo ""
        info "First run: $(bold "erenshor download --variant $variant")"
        exit $ERROR_DEPENDENCY
    fi

    # Show build info
    if [[ "$current_build" == "manual" ]]; then
        info "Game files detected (manually downloaded or incomplete manifest)"
    else
        info "Game build: $current_build"
    fi
    echo ""

    # Extract
    if ! assetripper_extract "$game_path" "$unity_path" "$variant"; then
        die $ERROR_PROCESS "Asset extraction failed"
    fi

    # Ensure symlink is created
    if ! symlink_check "$variant" >/dev/null 2>&1; then
        symlink_create "$variant"
    fi

    # Sync NuGet packages (in case extraction didn't copy them)
    if ! assetripper_sync_packages "$unity_path"; then
        warning "Failed to sync NuGet packages - Unity compilation may fail"
    fi

    # Setup export script
    if ! unity_setup_export_script "$unity_path"; then
        warning "Failed to setup export script - export command may not work"
    fi

    # Record state
    state_set_variant "$variant" "unity.last_extraction" "$(timestamp_iso)"
    state_set_variant "$variant" "unity.project_path" "$unity_path"

    # Calculate duration
    local end_time=$(date +%s)

    # Show summary
    echo ""
    success "Extraction complete in $(duration $start_time $end_time)"
    echo ""
    info "Unity project ready for export"
    echo ""
    info "Next step: $(bold "erenshor export")"
    echo ""
}

# Show help
show_extract_help() {
    cat << 'EOF'
erenshor extract - Extract assets with AssetRipper

USAGE:
    erenshor extract [OPTIONS]

DESCRIPTION:
    Extracts game assets from downloaded files using AssetRipper.
    Creates a Unity project with all decompiled scripts and assets.

    Note: AssetRipper is optional - the Unity project already exists
    in this repository. This command is mainly useful if you need to
    re-extract from a new game version.

OPTIONS:
    -f, --force          Re-extract even if already extracted
    --variant VARIANT    Extract specific variant (main, playtest, demo)
    -h, --help           Show this help message

EXAMPLES:
    # Extract assets (default variant: main)
    erenshor extract

    # Force re-extraction
    erenshor extract --force

    # Extract specific variant
    erenshor extract --variant playtest

SEE ALSO:
    erenshor update     Run full update pipeline
    erenshor download   Download game files
    erenshor export     Export data to database
EOF
}
