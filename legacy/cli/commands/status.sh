#!/usr/bin/env bash
# commands/status.sh - Show system status

command_main() {
    local variant="$(config_get default_variant)"
    local all_variants=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --variant)
                variant="$2"
                shift 2
                ;;
            --all-variants)
                all_variants=true
                shift
                ;;
            -h|--help)
                show_status_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor status --help' for usage."
                exit 1
                ;;
        esac
    done

    echo ""
    bold "=== Erenshor Data Mining Pipeline Status ==="
    echo ""

    # System dependencies
    bold "System:"
    check_command_status "Unity" "$(config_get unity.path)"
    check_command_status "SteamCMD" "steamcmd"
    check_command_status "AssetRipper" "$(config_get assetripper.path)"
    check_command_status "SQLite" "sqlite3"
    check_command_status "jq" "jq"
    echo ""

    # Projects
    bold "Projects:"
    local wiki_project=$(config_get paths.wiki_project)

    if [[ -d "$wiki_project" ]]; then
        success "Wiki: $wiki_project"
    else
        warning "Wiki: $wiki_project (not found)"
    fi
    echo ""

    # Show all variants or specific variant
    if [[ "$all_variants" == true ]]; then
        show_all_variants_status
    else
        if ! variant_validate "$variant"; then
            die $ERROR_ARGS "Invalid variant: $variant"
        fi
        show_variant_status "$variant"
    fi

    # Configuration
    bold "Configuration:"
    info "Config: $USER_CONFIG"
    info "Default Variant: $(variant_get_display_name "$(config_get default_variant)")"
    info "Logs: $(config_get paths.logs)"
    echo ""
}

show_variant_status() {
    local variant="$1"

    bold "Variant: $(variant_get_display_name "$variant")"

    # Get variant-specific paths
    local game_path=$(variant_get_path "$variant" "game")
    local unity_path=$(variant_get_path "$variant" "unity")
    local database_path=$(variant_get_path "$variant" "database")

    # Game status
    info "Game:"
    local build_id=$(steamcmd_get_current_build "$game_path")

    if [[ "$build_id" != "0" ]]; then
        success "  Build ID: $build_id"
        info "  Location: $game_path"
        info "  Size: $(du -sh "$game_path" 2>/dev/null | cut -f1 || echo "unknown")"
    else
        warning "  Not downloaded"
    fi

    # Unity project status
    info "Unity Project:"
    if [[ -d "$unity_path" ]]; then
        success "  Location: $unity_path"
        info "  Size: $(du -sh "$unity_path" 2>/dev/null | cut -f1 || echo "unknown")"
    else
        warning "  Not extracted: $unity_path"
    fi

    # Database status
    info "Database:"
    if [[ -f "$database_path" ]]; then
        success "  Location: $database_path"
        info "  Size: $(file_size "$database_path")"

        local entity_count=$(sqlite3 "$database_path" "SELECT COUNT(*) FROM sqlite_master WHERE type='table'" 2>/dev/null || echo "0")
        info "  Tables: $entity_count"
    else
        warning "  Not found: $database_path"
    fi

    # Backup status
    local backup_path=$(config_get_variant "$variant" "backups")
    if [[ -d "$backup_path" ]]; then
        local backup_count=$(find "$backup_path" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')
        if [[ $backup_count -gt 0 ]]; then
            local latest_backup=$(ls -1dt "$backup_path"/*/ 2>/dev/null | head -1 | sed 's:/$::')
            info "Backups:"
            info "  Count: $backup_count"
            if [[ -n "$latest_backup" ]]; then
                info "  Latest: $(basename "$latest_backup")"
            fi
        fi
    fi
    echo ""
}

show_all_variants_status() {
    bold "All Variants:"
    echo ""

    for v in $(variant_list); do
        if variant_is_enabled "$v"; then
            show_variant_status "$v"
        else
            bold "Variant: $(variant_get_display_name "$v")"
            warning "  Disabled"
            echo ""
        fi
    done
}

check_command_status() {
    local name="$1"
    local cmd="$2"

    if [[ -x "$cmd" ]] || command_exists "$cmd"; then
        if [[ -x "$cmd" ]]; then
            success "$name: $cmd"
        else
            success "$name: $(which "$cmd")"
        fi
    else
        error "$name: not found"
    fi
}

show_status_help() {
    cat << 'EOF'
erenshor status - Show system status

USAGE:
    erenshor status [OPTIONS]

DESCRIPTION:
    Shows the current status of the data mining pipeline including:
    - System dependencies
    - Game downloads
    - Unity projects
    - Database files
    - Configuration

OPTIONS:
    --variant VARIANT     Show status for specific variant (main, playtest, demo)
    --all-variants        Show status for all enabled variants
    -h, --help            Show this help message

EXAMPLES:
    # Show status for default variant
    erenshor status

    # Show status for specific variant
    erenshor status --variant playtest

    # Show status for all variants
    erenshor status --all-variants

SEE ALSO:
    erenshor check      Check for game updates
    erenshor update     Run full update pipeline
EOF
}
