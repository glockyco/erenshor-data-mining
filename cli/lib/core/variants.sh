#!/usr/bin/env bash
# lib/core/variants.sh - Variant management for multi-version support

# Module initialization
VARIANTS_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$VARIANTS_MODULE_DIR/logger.sh"
source "$VARIANTS_MODULE_DIR/errors.sh"
source "$VARIANTS_MODULE_DIR/config.sh"

# Get repo root (assumes we're in cli/lib/core/)
get_repo_root() {
    echo "$(cd "$VARIANTS_MODULE_DIR/../../.." && pwd)"
}

# List all available variants
variant_list() {
    local variants=("main" "playtest" "demo")
    printf '%s\n' "${variants[@]}"
}

# List only enabled variants from config
variant_list_enabled() {
    local enabled_variants=()

    for variant in main playtest demo; do
        if variant_is_enabled "$variant"; then
            enabled_variants+=("$variant")
        fi
    done

    if [[ ${#enabled_variants[@]} -eq 0 ]]; then
        # Default to main if nothing enabled
        echo "main"
    else
        printf '%s\n' "${enabled_variants[@]}"
    fi
}

# Check if variant is enabled in config
variant_is_enabled() {
    local variant="$1"

    # Main is always enabled
    if [[ "$variant" == "main" ]]; then
        return 0
    fi

    # Check config
    local enabled=$(config_get "variants.$variant.enabled" 2>/dev/null)
    [[ "$enabled" == "true" ]]
}

# Get variant-specific path
variant_get_path() {
    local variant="$1"
    local path_type="$2"  # game, unity, database
    local repo_root="$(get_repo_root)"

    case "$path_type" in
        game)
            echo "$repo_root/variants/$variant/game"
            ;;
        unity)
            echo "$repo_root/variants/$variant/unity"
            ;;
        database)
            echo "$repo_root/variants/$variant/erenshor-$variant.sqlite"
            ;;
        root)
            echo "$repo_root/variants/$variant"
            ;;
        *)
            log_error "Unknown path type: $path_type"
            return 1
            ;;
    esac
}

# Get variant-specific config value
variant_get_config() {
    local variant="$1"
    local key="$2"

    # Try variant-specific config first
    local value=$(config_get "variants.$variant.$key" 2>/dev/null)

    if [[ -n "$value" ]]; then
        echo "$value"
        return 0
    fi

    # Fall back to default
    config_get "$key" 2>/dev/null
}

# Get variant app_id for Steam
variant_get_app_id() {
    local variant="$1"

    case "$variant" in
        main)
            echo "2382520"  # Main game
            ;;
        playtest)
            echo "2924650"  # Playtest branch
            ;;
        demo)
            echo "2382520"  # Demo uses main app_id
            ;;
        *)
            log_error "Unknown variant: $variant"
            return 1
            ;;
    esac
}

# Get variant Steam branch
variant_get_branch() {
    local variant="$1"

    case "$variant" in
        main)
            echo ""  # Default branch
            ;;
        playtest)
            echo "playtest"
            ;;
        demo)
            echo "demo"
            ;;
        *)
            log_error "Unknown variant: $variant"
            return 1
            ;;
    esac
}

# Validate variant name
variant_validate() {
    local variant="$1"
    local valid_variants=("main" "playtest" "demo")

    for v in "${valid_variants[@]}"; do
        if [[ "$v" == "$variant" ]]; then
            return 0
        fi
    done

    log_error "Invalid variant: $variant"
    log_error "Valid variants: ${valid_variants[*]}"
    return 1
}

# Check if variant exists (has directory structure)
variant_exists() {
    local variant="$1"
    local variant_root="$(variant_get_path "$variant" root)"

    [[ -d "$variant_root" ]]
}

# Initialize variant directory structure
variant_init() {
    local variant="$1"
    local repo_root="$(get_repo_root)"
    local variant_root="$repo_root/variants/$variant"

    log_info "Initializing variant: $variant"

    # Create directories
    mkdir -p "$variant_root/game"
    mkdir -p "$variant_root/unity/Assets"

    # Create symlink
    source "$VARIANTS_MODULE_DIR/symlinks.sh"
    symlink_create "$variant"

    log_info "Variant initialized: $variant"
}

# Get variant status
variant_status() {
    local variant="$1"
    local variant_root="$(variant_get_path "$variant" root)"
    local game_dir="$(variant_get_path "$variant" game)"
    local unity_dir="$(variant_get_path "$variant" unity)"
    local database="$(variant_get_path "$variant" database)"

    echo "Variant: $variant"
    echo "  Enabled: $(variant_is_enabled "$variant" && echo "Yes" || echo "No")"
    echo "  Exists: $(variant_exists "$variant" && echo "Yes" || echo "No")"

    if variant_exists "$variant"; then
        echo "  Root: $variant_root"

        # Check game directory
        if [[ -d "$game_dir" ]]; then
            local game_size=$(du -sh "$game_dir" 2>/dev/null | cut -f1)
            echo "  Game: $game_size"
        else
            echo "  Game: Not downloaded"
        fi

        # Check Unity project
        if [[ -d "$unity_dir" ]]; then
            echo "  Unity: Exists"
        else
            echo "  Unity: Not extracted"
        fi

        # Check database
        if [[ -f "$database" ]]; then
            local db_size=$(du -sh "$database" 2>/dev/null | cut -f1)
            echo "  Database: $db_size"
        else
            echo "  Database: Not exported"
        fi

        # Check symlink
        source "$VARIANTS_MODULE_DIR/symlinks.sh"
        if symlink_check "$variant" >/dev/null 2>&1; then
            echo "  Symlink: Valid"
        else
            echo "  Symlink: Broken/Missing"
        fi
    fi

    echo ""
}

# Show status for all variants
variant_status_all() {
    echo ""
    echo "=== Variant Status ==="
    echo ""

    for variant in main playtest demo; do
        variant_status "$variant"
    done
}

# Get variant display name
variant_get_display_name() {
    local variant="$1"

    case "$variant" in
        main)
            echo "Main Game"
            ;;
        playtest)
            echo "Playtest"
            ;;
        demo)
            echo "Demo"
            ;;
        *)
            echo "$variant"
            ;;
    esac
}
