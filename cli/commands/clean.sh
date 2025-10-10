#!/usr/bin/env bash
# commands/clean.sh - Clean up old files

# Cleanup configuration constants
readonly CLEAN_LOG_RETENTION_DAYS=30

command_main() {
    local all=false
    local dry_run=false
    local variant="$(config_get default_variant)"
    local all_variants=false
    local original_args=("$@")

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            --all|-a)
                all=true
                shift
                ;;
            --dry-run|-n)
                dry_run=true
                shift
                ;;
            --variant)
                variant="$2"
                shift 2
                ;;
            --all-variants)
                all_variants=true
                shift
                ;;
            -h|--help)
                show_clean_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Handle --all-variants
    if [[ "$all_variants" == true ]]; then
        variant_for_each_enabled "cleaned" "$0" "${original_args[@]}"
    fi

    # Validate variant
    if ! variant_validate "$variant"; then
        die $ERROR_ARGS "Invalid variant: $variant"
    fi

    echo ""
    info "Cleaning up old files ($(variant_get_display_name "$variant"))..."
    echo ""

    if [[ "$dry_run" == true ]]; then
        warning "DRY RUN MODE - No files will be deleted"
        echo ""
    fi

    local removed=0

    # Get variant-specific paths
    local unity_path=$(variant_get_path "$variant" "unity")

    # Clean old logs (keep last N days)
    local logs_dir=$(config_get paths.logs)
    if [[ -d "$logs_dir" ]]; then
        info "Cleaning old logs (>$CLEAN_LOG_RETENTION_DAYS days)..."
        local old_logs=$(find "$logs_dir" -type f -name "*.log" -mtime +$CLEAN_LOG_RETENTION_DAYS 2>/dev/null)

        if [[ -n "$old_logs" ]]; then
            local count=$(echo "$old_logs" | wc -l)

            if [[ "$dry_run" != true ]]; then
                echo "$old_logs" | xargs rm -f
                success "Removed $count old log file(s)"
            else
                info "Would remove $count old log file(s)"
            fi

            ((removed += count))
        fi
    fi

    # Clean incomplete SteamCMD downloads
    local game_path=$(variant_get_path "$variant" "game")
    if [[ -d "$game_path/steamapps/downloading" ]]; then
        info "Cleaning incomplete SteamCMD downloads..."
        local dl_size=$(du -sh "$game_path/steamapps/downloading" 2>/dev/null | cut -f1 || echo "unknown")
        if [[ "$dry_run" != true ]]; then
            steamcmd_clean_incomplete "$game_path"
            success "Cleaned $dl_size of incomplete downloads"
        else
            info "Would clean $dl_size of incomplete downloads"
        fi
    fi

    # Clean AssetRipper extraction artifacts for this variant
    if [[ "$all" == true ]]; then
        info "Cleaning AssetRipper artifacts..."
        if [[ "$dry_run" != true ]]; then
            assetripper_clean "$unity_path"
            success "Cleaned extraction artifacts"
        else
            info "Would clean extraction artifacts"
        fi
    fi

    # Clean old output databases for this variant
    if [[ "$all" == true ]]; then
        info "Cleaning old database exports..."
        if [[ "$dry_run" != true ]]; then
            database_clean_variant "$variant"
            success "Cleaned old database exports"
        else
            info "Would clean old database exports"
        fi
    fi

    echo ""
    if [[ $removed -gt 0 ]]; then
        celebrate "Cleaned up $removed file(s)"
    else
        info "Nothing to clean"
    fi
}

show_clean_help() {
    cat << 'EOF'
erenshor clean - Clean up old files

USAGE:
    erenshor clean [OPTIONS]

DESCRIPTION:
    Removes old logs, backups, and temporary files to free up disk space.
    Keeps recent files based on configuration.

OPTIONS:
    -a, --all             Also clean extraction artifacts and old exports
    -n, --dry-run         Show what would be deleted without deleting
    --variant VARIANT     Clean files for specific variant (main, playtest, demo)
    --all-variants        Clean files for all enabled variants
    -h, --help            Show this help message

WHAT GETS CLEANED:
    - Log files older than $CLEAN_LOG_RETENTION_DAYS days
    - Incomplete SteamCMD downloads
    - AssetRipper extraction artifacts (with --all)
    - Old database exports (with --all)

EXAMPLES:
    # Clean old files (default variant: main)
    erenshor clean

    # Preview what will be cleaned
    erenshor clean --dry-run

    # Clean everything including artifacts
    erenshor clean --all

    # Clean specific variant
    erenshor clean --variant playtest

    # Clean all variants
    erenshor clean --all-variants --dry-run

SEE ALSO:
    erenshor status     Show disk space usage
EOF
}
