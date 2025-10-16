#!/usr/bin/env bash
# commands/export.sh - Export data to SQLite via Unity

# Command entry point
command_main() {
    local entities="all"
    local output=""
    local variant="$(config_get default_variant)"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -e|--entities)
                entities="$2"
                shift 2
                ;;
            -o|--output)
                output="$2"
                shift 2
                ;;
            --variant)
                variant="$2"
                shift 2
                ;;
            -h|--help)
                show_export_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor export --help' for usage."
                exit 1
                ;;
        esac
    done

    # Validate variant
    if ! variant_validate "$variant"; then
        die $ERROR_ARGS "Invalid variant: $variant"
    fi

    # Set module name for logging
    export LOG_MODULE="export"

    # Start timer
    local start_time=$(date +%s)

    # Show header
    echo ""
    celebrate "Exporting Game Data ($(variant_get_display_name "$variant"))"
    echo ""

    # Get variant-specific paths
    local unity_project=$(variant_get_path "$variant" "unity")
    local database_path=$(variant_get_path "$variant" "database")

    # Check if Unity project exists
    if [[ ! -d "$unity_project" ]]; then
        error "Unity project not found: $unity_project"
        echo ""
        info "First run: $(bold "erenshor extract --variant $variant")"
        exit $ERROR_DEPENDENCY
    fi

    # Export
    info "Entities: $entities"
    echo ""

    # Get output path
    if [[ -z "$output" ]]; then
        output="$database_path"
    fi

    # Backup existing database before overwriting
    if [[ -f "$output" ]]; then
        info "Backing up existing database..."
        local backup_dir=$(database_backup "$output" "$variant")
        if [[ -n "$backup_dir" ]]; then
            # Also backup game scripts
            backup_game_scripts "$backup_dir" "$unity_project"
            success "Backup created: $backup_dir"
        else
            warning "Backup failed, but continuing with export"
        fi
        echo ""
    fi

    # Delete existing database to avoid ID conflicts
    if [[ -f "$output" ]]; then
        log_debug "Removing existing database: $output"
        rm "$output"
    fi

    if ! unity_export "$unity_project" "$output" "$entities" "$variant"; then
        die $ERROR_PROCESS "Unity export failed"
    fi

    # Validate
    if ! database_validate "$output"; then
        die $ERROR_VALIDATION "Database validation failed"
    fi

    # Record state
    local db_size=$(stat -f%z "$output" 2>/dev/null || echo 0)
    local entity_counts=$(database_stats_json "$output")
    state_record_variant_export "$variant" "$output" "$db_size" "$entity_counts"

    # Calculate duration
    local end_time=$(date +%s)

    # Show summary
    echo ""
    success "Export complete in $(duration $start_time $end_time)"
    echo ""
    info "Database: $output"
    info "Size: $(file_size "$output")"
    echo ""
    info "Statistics:"
    db_stats "$output" | while IFS='|' read -r table count; do
        echo "  $table: $count"
    done
    echo ""
    info "Next step: $(bold "erenshor deploy --variant $variant")"
    echo ""
}

# Show help
show_export_help() {
    cat << 'EOF'
erenshor export - Export data to SQLite via Unity

USAGE:
    erenshor export [OPTIONS]

DESCRIPTION:
    Opens the Unity project and exports all game data to a SQLite database.
    This uses the custom Unity Editor scripts in src/Assets/Editor/ExportSystem/.

OPTIONS:
    -e, --entities LIST   Export specific entity types (comma-separated)
    -o, --output PATH     Output database path (default: from config)
    --variant VARIANT     Export from specific variant (main, playtest, demo)
    -h, --help            Show this help message

ENTITY TYPES:
    items, characters, quests, spells, skills, factions, loot,
    spawns, zones, crafting, gathering, achievements, classes

EXAMPLES:
    # Export all entities (default variant: main)
    erenshor export

    # Export specific entities only
    erenshor export --entities items,spells,characters

    # Export to custom location
    erenshor export --output /tmp/test.sqlite

    # Export from specific variant
    erenshor export --variant playtest

SEE ALSO:
    erenshor update     Run full update pipeline
    erenshor extract    Extract game assets
    erenshor deploy     Deploy database to wiki
EOF
}
