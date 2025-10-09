#!/usr/bin/env bash
# commands/deploy.sh - Deploy database to wiki project

# Command entry point
command_main() {
    local skip_backup=false
    local source=""
    local variant="$(config_get default_variant)"
    local all_variants=false
    local target="sqlite"
    local dry_run=false
    local sheets=()
    local original_args=("$@")

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --no-backup)
                skip_backup=true
                shift
                ;;
            -s|--source)
                source="$2"
                shift 2
                ;;
            --variant)
                variant="$2"
                shift 2
                ;;
            --all-variants)
                all_variants=true
                shift
                ;;
            -t|--target)
                target="$2"
                shift 2
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --sheet)
                sheets+=("$2")
                shift 2
                ;;
            -h|--help)
                show_deploy_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor deploy --help' for usage."
                exit 1
                ;;
        esac
    done

    # Handle --all-variants
    if [[ "$all_variants" == true ]]; then
        variant_for_each_enabled "deployed" "$0" "${original_args[@]}"
    fi

    # Validate variant
    if ! variant_validate "$variant"; then
        die $ERROR_GENERAL "Invalid variant: $variant"
    fi

    # Validate target
    case "$target" in
        sqlite|sheets)
            # Valid targets
            ;;
        *)
            error "Invalid target: $target"
            echo "Valid targets: sqlite, sheets"
            exit 1
            ;;
    esac

    # Set module name for logging
    export LOG_MODULE="deploy"

    # Start timer
    local start_time=$(date +%s)

    # Route to appropriate deployment function
    case "$target" in
        sqlite)
            deploy_sqlite "$variant" "$source" "$skip_backup" "$start_time"
            ;;
        sheets)
            deploy_sheets "$variant" "$dry_run" "${sheets[@]}"
            ;;
    esac
}

# Deploy to SQLite (existing behavior)
deploy_sqlite() {
    local variant="$1"
    local source="$2"
    local skip_backup="$3"
    local start_time="$4"

    # Show header
    echo ""
    celebrate "Deploying Database to SQLite ($(variant_get_display_name "$variant"))"
    echo ""

    # Get variant-specific paths
    local database_path=$(variant_get_path "$variant" "database")

    # Get source database
    if [[ -z "$source" ]]; then
        source="$database_path"
    fi

    # Check if source exists
    if [[ ! -f "$source" ]]; then
        error "Database not found: $source"
        echo ""
        info "First run: $(bold "erenshor export --variant $variant")"
        exit $ERROR_DEPENDENCY
    fi

    # Validate source
    if ! database_validate "$source"; then
        die $ERROR_VALIDATION "Source database validation failed"
    fi

    # Get wiki database path - preserve variant-specific filename
    local source_filename=$(basename "$source")
    local wiki_db="$(config_get paths.wiki_project)/$source_filename"

    # Backup if enabled
    if [[ "$skip_backup" != true ]]; then
        if [[ -f "$wiki_db" ]]; then
            info "Creating backup..."
            database_backup "$wiki_db"
            echo ""
        fi
    fi

    # Deploy
    if ! database_deploy "$source" "$wiki_db"; then
        die $ERROR_PROCESS "Database deployment failed"
    fi

    # Calculate duration
    local end_time=$(date +%s)

    # Show summary
    echo ""
    success "Deployment complete in $(duration $start_time $end_time)"
    echo ""

    info "Deployed to: $wiki_db"
    info "Size: $(file_size "$wiki_db")"
    echo ""
}

# Deploy to Google Sheets
deploy_sheets() {
    local variant="$1"
    local dry_run="$2"
    shift 2
    local sheets=("$@")

    # Show header
    echo ""
    celebrate "Deploying to Google Sheets ($(variant_get_display_name "$variant"))"
    echo ""

    # Build Python CLI arguments
    local python_args=(sheets deploy --variant "$variant")

    # Add dry-run flag if specified
    if [[ "$dry_run" == true ]]; then
        python_args+=(--dry-run)
    fi

    # Add specific sheets if specified
    for sheet in "${sheets[@]}"; do
        if [[ -n "$sheet" ]]; then
            python_args+=(--sheet "$sheet")
        fi
    done

    # Execute Python CLI
    info "Running: python -m erenshor.cli.main ${python_args[*]}"
    echo ""

    if ! python_exec "${python_args[@]}"; then
        error "Google Sheets deployment failed"
        exit $ERROR_PROCESS
    fi

    echo ""
    success "Google Sheets deployment complete"
    echo ""
}

# Show help
show_deploy_help() {
    cat << 'EOF'
erenshor deploy - Deploy data to various targets

USAGE:
    erenshor deploy [OPTIONS]

DESCRIPTION:
    Deploy exported game data to various targets including SQLite database,
    Google Sheets, or other destinations. Default target is SQLite.

OPTIONS:
    -t, --target TARGET   Deployment target (sqlite, sheets) [default: sqlite]
    --variant VARIANT     Deploy specific variant (main, playtest, demo)
    --all-variants        Deploy all enabled variants sequentially
    --dry-run             Preview without uploading (sheets only)
    --sheet NAME          Specific sheet to deploy (sheets only, can be repeated)
    -s, --source PATH     Source database path (sqlite only)
    --no-backup           Skip database backup (sqlite only)
    -h, --help            Show this help message

TARGETS:
    sqlite                Copy SQLite database to wiki project
    sheets                Deploy to Google Sheets

EXAMPLES:
    # Deploy latest export to SQLite (default)
    erenshor deploy

    # Deploy to Google Sheets (all sheets)
    erenshor deploy --target sheets

    # Deploy specific sheets with dry-run
    erenshor deploy --target sheets --sheet items --sheet characters --dry-run

    # Deploy playtest variant to sheets
    erenshor deploy --target sheets --variant playtest

    # Deploy from custom SQLite location
    erenshor deploy --target sqlite --source /tmp/test.sqlite

    # Deploy SQLite without backup
    erenshor deploy --target sqlite --no-backup

    # Deploy all variants to sheets
    erenshor deploy --target sheets --all-variants

SEE ALSO:
    erenshor update     Run full update pipeline
    erenshor export     Export data to database
    erenshor status     Show deployment status
EOF
}
