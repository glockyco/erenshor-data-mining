#!/usr/bin/env bash
# commands/update.sh - Main update command

# Command entry point
command_main() {
    local force=false
    local skip_download=false
    local entities="all"
    local dry_run=false
    local skip_backup=false
    local variant="$(config_get default_variant)"
    local all_variants=false
    local original_args=("$@")

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--force)
                force=true
                shift
                ;;
            -s|--skip-download)
                skip_download=true
                shift
                ;;
            -e|--entities)
                entities="$2"
                shift 2
                ;;
            -n|--dry-run)
                dry_run=true
                shift
                ;;
            --no-backup)
                skip_backup=true
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
                show_update_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor update --help' for usage."
                exit 1
                ;;
        esac
    done

    # Handle --all-variants
    if [[ "$all_variants" == true ]]; then
        variant_for_each_enabled "updated" "$0" "${original_args[@]}"
    fi

    # Validate variant
    if ! variant_validate "$variant"; then
        die $ERROR_ARGS "Invalid variant: $variant"
    fi

    # Set module name for logging
    export LOG_MODULE="update"

    # Start timer
    local start_time=$(date +%s)

    # Show header
    echo ""
    celebrate "Erenshor Data Mining Pipeline ($(variant_get_display_name "$variant"))"
    echo ""

    if [[ "$dry_run" == true ]]; then
        info "DRY RUN MODE - No changes will be made"
        echo ""
    fi

    # Get variant-specific paths
    local app_id=$(variant_get_config "$variant" "app_id")
    local game_path=$(variant_get_path "$variant" "game")
    local unity_path=$(variant_get_path "$variant" "unity")
    local database_path=$(variant_get_path "$variant" "database")

    # Stage 1: Check for updates
    step_progress 1 5 "Checking for updates"
    if ! steamcmd_check_update "$game_path"; then
        if [[ "$force" != true ]]; then
            success "No updates needed"
            exit 0
        fi
    fi

    # Stage 2: Download game (unless skipped)
    if [[ "$skip_download" != true ]]; then
        step_progress 2 5 "Downloading game files"

        if [[ "$dry_run" != true ]]; then
            if ! steamcmd_download "$app_id" "$game_path"; then
                die $ERROR_PROCESS "Game download failed"
            fi
            success "Download complete"

            # Record state
            local build_id=$(steamcmd_get_current_build "$game_path")
            local game_size=$(steamcmd_get_game_size "$game_path")
            state_record_variant_game "$variant" "$build_id" "$game_path" "$game_size"
        else
            info "Would download game via SteamCMD"
        fi
    else
        info "Skipping download (--skip-download)"
    fi

    # Stage 3: Extract assets
    step_progress 3 5 "Extracting assets with AssetRipper"

    if [[ "$dry_run" != true ]]; then
        if ! assetripper_extract "$game_path" "$unity_path"; then
            die $ERROR_PROCESS "Asset extraction failed"
        fi
        success "Extraction complete"
    else
        info "Would extract assets with AssetRipper"
    fi

    # Stage 4: Export to database
    step_progress 4 5 "Exporting data to SQLite"

    if [[ "$dry_run" != true ]]; then
        if ! unity_export "$unity_path" "$database_path" "$entities"; then
            die $ERROR_PROCESS "Unity export failed"
        fi
        success "Export complete"

        # Validate
        if ! database_validate "$database_path"; then
            die $ERROR_VALIDATION "Database validation failed"
        fi
    else
        info "Would export data via Unity to SQLite"
    fi

    # Stage 5: Deploy to wiki
    step_progress 5 5 "Deploying to wiki project"

    if [[ "$dry_run" != true ]]; then
        # Use variant-specific filename (e.g., erenshor-main.sqlite, erenshor-playtest.sqlite)
        local source_filename=$(basename "$database_path")
        local wiki_db="$(config_get paths.wiki_project)/$source_filename"

        # Backup if enabled
        if [[ "$skip_backup" != true ]]; then
            database_backup "$wiki_db"
        fi

        if ! database_deploy "$database_path" "$wiki_db"; then
            die $ERROR_PROCESS "Database deployment failed"
        fi
        success "Deployment complete"

        # Record state
        local db_size=$(stat -f%z "$database_path" 2>/dev/null || echo 0)
        local entity_counts=$(database_stats_json "$database_path")
        state_record_variant_export "$variant" "$database_path" "$db_size" "$entity_counts"
    else
        info "Would deploy database to wiki project"
    fi

    # Calculate duration
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    # Record pipeline state
    state_record_pipeline "success" "$duration" "{}"

    # Show summary
    echo ""
    celebrate "Success! Pipeline completed in $(duration $start_time $end_time)"
    echo ""

    if [[ "$dry_run" != true ]]; then
        # Use the same wiki_db path as above
        local source_filename=$(basename "$database_path")
        local wiki_db="$(config_get paths.wiki_project)/$source_filename"
        info "Database: $wiki_db"
        info "Size: $(file_size "$wiki_db")"
        echo ""
        info "Statistics:"
        db_stats "$wiki_db" | while IFS='|' read -r table count; do
            echo "  $table: $count"
        done
    fi

    echo ""
}

# Show help
show_update_help() {
    cat << 'EOF'
erenshor update - Update game data and export to database

USAGE:
    erenshor update [OPTIONS]

DESCRIPTION:
    Downloads the latest game files, extracts assets, exports data to SQLite,
    and deploys to the wiki project. This is the main command for keeping your
    game data up-to-date.

OPTIONS:
    -f, --force           Force update even if no changes detected
    -s, --skip-download   Skip game download (use existing files)
    -e, --entities LIST   Export specific entity types (comma-separated)
    -n, --dry-run         Show what would happen without doing it
    --no-backup           Skip database backup
    --variant VARIANT     Update specific variant (main, playtest, demo)
    --all-variants        Update all enabled variants sequentially
    -h, --help            Show this help message

EXAMPLES:
    # Full update (default variant: main)
    erenshor update

    # Update specific entities only
    erenshor update --entities items,spells,characters

    # Quick update using existing game files
    erenshor update --skip-download

    # Preview what will happen
    erenshor update --dry-run

    # Update specific variant
    erenshor update --variant playtest

    # Update all enabled variants
    erenshor update --all-variants

SEE ALSO:
    erenshor check      Check for updates without downloading
    erenshor download   Download game files only
    erenshor status     Show current system status
EOF
}
