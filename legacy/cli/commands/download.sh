#!/usr/bin/env bash
# commands/download.sh - Download game files via SteamCMD

# Command entry point
command_main() {
    local force=false
    local validate=false
    local variant="$(config_get default_variant)"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                force=true
                shift
                ;;
            --validate)
                validate=true
                shift
                ;;
            --variant)
                variant="$2"
                shift 2
                ;;
            -h|--help)
                show_download_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor download --help' for usage."
                exit 1
                ;;
        esac
    done

    # Validate variant
    if ! variant_validate "$variant"; then
        die $ERROR_ARGS "Invalid variant: $variant"
    fi

    # Set module name for logging
    export LOG_MODULE="download"

    # Start timer
    local start_time=$(date +%s)

    # Show header
    echo ""
    celebrate "Downloading Game Files ($(variant_get_display_name "$variant"))"
    echo ""

    # Get variant-specific paths and config
    local app_id=$(variant_get_config "$variant" "app_id")
    local game_path=$(variant_get_path "$variant" "game")

    # Check if already downloaded
    local current_build=$(steamcmd_get_current_build "$game_path")

    if [[ "$current_build" != "0" && "$force" != true ]]; then
        if [[ "$current_build" == "manual" ]]; then
            info "Game already downloaded (manual/incomplete download detected)"
        else
            info "Game already downloaded (build $current_build)"
        fi
        echo ""
        info "Use $(bold "--force") to re-download"
        exit 0
    fi

    # Show validation mode info
    if [[ "$validate" == true ]]; then
        echo ""
        info "Running with $(bold "--validate") flag: Full file validation will be performed"
        info "This may take longer but ensures file integrity"
        echo ""
    fi

    # Download
    if ! steamcmd_download "$app_id" "$game_path" "$variant" "$validate"; then
        die $ERROR_PROCESS "Game download failed"
    fi

    # Capture build metadata
    local build_id=$(steamcmd_get_current_build "$game_path")
    local game_size=$(steamcmd_get_game_size "$game_path")
    local branch="public"
    local build_timestamp=$(steamcmd_get_build_timestamp "$app_id" "$branch")
    local manifest_id=$(steamcmd_get_manifest_id "$game_path" "$app_id")
    local download_size_bytes=$(steamcmd_get_download_size "$app_id" "$branch")

    # Log metadata for debugging
    log_debug "Build metadata captured:"
    log_debug "  build_id: $build_id"
    log_debug "  build_timestamp: $build_timestamp"
    log_debug "  manifest_id: $manifest_id"
    log_debug "  download_size_bytes: $download_size_bytes"

    # Record state with all metadata
    state_record_variant_game "$variant" "$build_id" "$game_path" "$game_size" \
        "$build_timestamp" "$branch" "$manifest_id" "$download_size_bytes"

    # Calculate duration
    local end_time=$(date +%s)

    # Show summary
    echo ""
    success "Download complete in $(duration $start_time $end_time)"
    echo ""
    info "Build: $build_id"
    info "Size: ${game_size}MB"
    echo ""
    info "Next step: $(bold "erenshor extract")"
    echo ""
}

# Show help
show_download_help() {
    cat << 'EOF'
erenshor download - Download game files via SteamCMD

USAGE:
    erenshor download [OPTIONS]

DESCRIPTION:
    Downloads Erenshor game files using SteamCMD. This is the first step
    in the data mining pipeline.

    By default, SteamCMD performs incremental updates (only changed files).
    Use --validate for full file verification if you suspect corruption.

OPTIONS:
    -f, --force          Re-download even if already downloaded
    --validate           Perform full file validation (slower, but ensures integrity)
    --variant VARIANT    Download specific variant (main, playtest, demo)
    -h, --help           Show this help message

EXAMPLES:
    # Download game (default variant: main)
    erenshor download

    # Force re-download
    erenshor download --force

    # Download with full file validation
    erenshor download --validate

    # Download specific variant with validation
    erenshor download --variant playtest --validate

NOTES:
    --validate flag causes SteamCMD to verify all game files against Steam's
    servers. This is slower but recommended if you suspect file corruption or
    want to ensure a clean install.

SEE ALSO:
    erenshor update     Run full update pipeline
    erenshor check      Check current build
    erenshor extract    Extract assets from downloaded game
EOF
}
