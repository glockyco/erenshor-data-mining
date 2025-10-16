#!/usr/bin/env bash
# lib/modules/database.sh - Database operations

# Guard against multiple sourcing
[[ -n "${DATABASE_MODULE_LOADED:-}" ]] && return 0
readonly DATABASE_MODULE_LOADED=1

# Module initialization
DATABASE_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$DATABASE_MODULE_DIR/../core/logger.sh"
source "$DATABASE_MODULE_DIR/../core/errors.sh"
source "$DATABASE_MODULE_DIR/../core/config.sh"
source "$DATABASE_MODULE_DIR/../core/utils.sh"
source "$DATABASE_MODULE_DIR/../core/state.sh"

# Backup database
# Usage: database_backup <db_path> [variant]
# Returns: backup directory path on success, empty on failure
database_backup() {
    local db_path="$1"
    local variant="${2:-main}"
    local backups_root=$(config_get_variant "$variant" "backups")

    if [[ -z "$db_path" ]]; then
        log_error "Database path is required"
        return 1
    fi

    if [[ ! -f "$db_path" ]]; then
        log_debug "No database to backup: $db_path"
        return 0
    fi

    # Validate variant
    if [[ -n "$variant" ]] && ! variant_validate "$variant" 2>/dev/null; then
        log_error "Invalid variant: $variant"
        return 1
    fi

    # Validate backups path
    if [[ -z "$backups_root" ]]; then
        log_error "Backup path not configured for variant: $variant"
        return 1
    fi

    mkdir -p "$backups_root"

    # Get build metadata from state for naming
    local build_id=$(state_get_variant "$variant" "game.build_id" "")
    local build_timestamp=$(state_get_variant "$variant" "game.build_timestamp" "")

    # Generate timestamp for directory name
    local file_timestamp=""
    if [[ -n "$build_timestamp" && "$build_timestamp" != "null" ]]; then
        # Convert ISO 8601 to YYYYMMDD-HHMMSS format
        # Example: 2025-10-09T23:32:23Z -> 20251009-233223
        # Requires: sed with -E flag (macOS/BSD/GNU)
        file_timestamp=$(echo "$build_timestamp" | sed -E 's/([0-9]{4})-([0-9]{2})-([0-9]{2})T([0-9]{2}):([0-9]{2}):([0-9]{2})Z/\1\2\3-\4\5\6/')

        # Validate conversion succeeded
        if [[ ! "$file_timestamp" =~ ^[0-9]{8}-[0-9]{6}$ ]]; then
            log_error "Failed to convert build timestamp (sed -E not supported?): $build_timestamp"
            return 1
        fi
    else
        # Fallback to current timestamp
        file_timestamp=$(timestamp_file)
    fi

    # Format: YYYYMMDD-HHMMSS_buildBUILDID/
    local backup_dir
    if [[ -n "$build_id" && "$build_id" != "null" ]]; then
        backup_dir="$backups_root/${file_timestamp}_build${build_id}"
    else
        backup_dir="$backups_root/${file_timestamp}"
    fi

    # Create backup directory structure
    mkdir -p "$backup_dir/db"

    # Copy database to db/erenshor.sqlite (simple name)
    local backup_file="$backup_dir/db/erenshor.sqlite"
    log_info "Creating backup: $backup_file"

    if ! cp "$db_path" "$backup_file"; then
        log_error "Failed to backup database"
        return 1
    fi

    # Return backup directory path for script backup
    echo "$backup_dir"
    return 0
}

# Backup game scripts from Unity project
# Usage: backup_game_scripts <backup_dir> <unity_path>
backup_game_scripts() {
    local backup_dir="$1"
    local unity_path="$2"

    if [[ -z "$backup_dir" ]]; then
        log_error "Backup directory is required"
        return 1
    fi

    if [[ -z "$unity_path" ]]; then
        log_error "Unity path is required"
        return 1
    fi

    if [[ ! -d "$unity_path" ]]; then
        log_warn "Unity project not found, skipping script backup: $unity_path"
        return 0
    fi

    # Source: {unity_path}/Assets/Scripts/Assembly-CSharp/
    local scripts_source="$unity_path/Assets/Scripts/Assembly-CSharp"

    if [[ ! -d "$scripts_source" ]]; then
        log_warn "Assembly-CSharp folder not found, skipping script backup: $scripts_source"
        return 0
    fi

    # Target: {backup_dir}/src/ (with internal structure preserved)
    local scripts_target="$backup_dir/src"

    log_info "Backing up game scripts to: $scripts_target"

    # Create target directory
    mkdir -p "$scripts_target"

    # Copy all .cs files with directory structure preserved
    # Strip the Assembly-CSharp prefix from paths
    if ! rsync -a --include='*/' --include='*.cs' --exclude='*' "$scripts_source/" "$scripts_target/"; then
        log_error "Failed to backup game scripts"
        return 1
    fi

    # Count how many files were backed up
    local file_count=$(find "$scripts_target" -type f -name "*.cs" 2>/dev/null | wc -l | tr -d ' ')

    log_info "Backed up $file_count C# script files"
    return 0
}

# Validate database
database_validate() {
    local db_path="$1"

    log_info "Validating database: $db_path"

    if ! verify_database "$db_path"; then
        log_error "Database validation failed"
        return $ERROR_VALIDATION
    fi

    # Get stats
    local stats=$(db_stats "$db_path")
    log_info "Database statistics:"
    echo "$stats" | while IFS='|' read -r table count; do
        log_info "  $table: $count rows"
    done

    return 0
}

# Deploy database to wiki project
# Usage: database_deploy [source_db] [target_db]
database_deploy() {
    local source_db="$1"
    local target_db="${2:-$(config_get paths.wiki_project)/erenshor.sqlite}"

    log_info "Deploying database to wiki project..."
    log_debug "Source: $source_db"
    log_debug "Target: $target_db"

    # Verify source
    if ! verify_database "$source_db"; then
        log_error "Source database is invalid"
        return $ERROR_VALIDATION
    fi

    # Copy to target
    cp "$source_db" "$target_db"

    # Verify deployment
    if ! verify_database "$target_db"; then
        log_error "Deployed database validation failed"
        # Note: We deliberately don't auto-restore from backup here.
        # If deployment fails, it's better to fail loudly and let the user
        # investigate the root cause rather than silently restoring.
        return $ERROR_VALIDATION
    fi

    log_info "Database deployed successfully"
    return 0
}

# Get database statistics as JSON
database_stats_json() {
    local db_path="$1"

    if [[ ! -f "$db_path" ]]; then
        echo "{}"
        return
    fi

    local stats=$(db_stats "$db_path")
    local json="{"
    local first=true

    # Use process substitution to avoid subshell issue with pipe
    while IFS='|' read -r table count; do
        if [[ "$first" != true ]]; then
            json="$json,"
        fi
        json="$json\"$table\": $count"
        first=false
    done < <(echo "$stats")

    json="$json}"
    echo "$json"
}

# Compare two databases
database_compare() {
    local db1="$1"
    local db2="$2"

    log_info "Comparing databases..."

    if [[ ! -f "$db1" ]]; then
        log_error "Database not found: $db1"
        return 1
    fi

    if [[ ! -f "$db2" ]]; then
        log_error "Database not found: $db2"
        return 1
    fi

    local stats1=$(db_stats "$db1")
    local stats2=$(db_stats "$db2")

    echo "Database 1: $db1"
    echo "$stats1" | while IFS='|' read -r table count; do
        echo "  $table: $count"
    done

    echo ""
    echo "Database 2: $db2"
    echo "$stats2" | while IFS='|' read -r table count; do
        echo "  $table: $count"
    done
}

# Clean old databases for specific variant
database_clean_variant() {
    local variant="$1"
    local database_path=$(variant_get_path "$variant" "database")
    local database_dir=$(dirname "$database_path")

    log_info "Cleaning old database files for variant: $variant"

    # Remove old variant-specific databases (keep last 3)
    if [[ -d "$database_dir" ]]; then
        local db_files=$(ls -1t "$database_dir"/erenshor_*.sqlite 2>/dev/null)
        local count=$(echo "$db_files" | wc -l)

        if [[ $count -gt 3 ]]; then
            echo "$db_files" | tail -n +4 | xargs rm -f
            log_info "Removed $((count - 3)) old database file(s)"
        fi
    fi
}
