#!/usr/bin/env bash
# commands/deploy.sh - Deploy database to wiki project

# Command entry point
command_main() {
    local skip_backup=false
    local source=""
    local variant="$(config_get default_variant)"
    local all_variants=false
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
        echo ""
        celebrate "Deploying All Variants"
        echo ""

        local deployed=0
        local failed=0

        for v in $(variant_list); do
            if variant_is_enabled "$v"; then
                info "Deploying variant: $(variant_get_display_name "$v")"
                echo ""

                # Remove --all-variants flag and add specific variant
                local variant_args=()
                for arg in "${original_args[@]}"; do
                    if [[ "$arg" != "--all-variants" ]]; then
                        variant_args+=("$arg")
                    fi
                done

                if VARIANT="$v" "$0" "${variant_args[@]}" --variant "$v"; then
                    ((deployed++))
                else
                    ((failed++))
                fi
                echo ""
            fi
        done

        echo ""
        if [[ $failed -eq 0 ]]; then
            celebrate "Successfully deployed $deployed variant(s)"
        else
            warning "Deployed $deployed variant(s), $failed failed"
        fi
        echo ""
        exit 0
    fi

    # Validate variant
    if ! variant_validate "$variant"; then
        die $ERROR_ARGS "Invalid variant: $variant"
    fi

    # Set module name for logging
    export LOG_MODULE="deploy"

    # Start timer
    local start_time=$(date +%s)

    # Show header
    echo ""
    celebrate "Deploying Database ($(variant_get_display_name "$variant"))"
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

# Show help
show_deploy_help() {
    cat << 'EOF'
erenshor deploy - Deploy database to wiki project

USAGE:
    erenshor deploy [OPTIONS]

DESCRIPTION:
    Copies the exported SQLite database to the wiki project directory.
    Creates a backup of the existing database before overwriting.

OPTIONS:
    -s, --source PATH     Source database path (default: from config)
    --variant VARIANT     Deploy specific variant (main, playtest, demo)
    --all-variants        Deploy all enabled variants sequentially
    --no-backup           Skip database backup
    -h, --help            Show this help message

EXAMPLES:
    # Deploy latest export (default variant: main)
    erenshor deploy

    # Deploy from custom location
    erenshor deploy --source /tmp/test.sqlite

    # Deploy without backup
    erenshor deploy --no-backup

    # Deploy specific variant
    erenshor deploy --variant playtest

    # Deploy all enabled variants
    erenshor deploy --all-variants

SEE ALSO:
    erenshor update     Run full update pipeline
    erenshor export     Export data to database
    erenshor status     Show deployment status
EOF
}
