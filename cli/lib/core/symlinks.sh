#!/usr/bin/env bash
# lib/core/symlinks.sh - Symlink management for variant Unity projects

# Module initialization
SYMLINKS_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SYMLINKS_MODULE_DIR/logger.sh"
source "$SYMLINKS_MODULE_DIR/errors.sh"

# Get repo root (assumes we're in cli/lib/core/)
get_repo_root() {
    echo "$(cd "$SYMLINKS_MODULE_DIR/../../.." && pwd)"
}

# Check symlink for a specific variant
# Returns: 0 if valid, 1 if broken/missing, 2 if wrong target
symlink_check() {
    local variant="$1"
    local repo_root="$(get_repo_root)"
    local editor_link="$repo_root/variants/$variant/unity/Assets/Editor"
    local expected_target="../../../../src/Assets/Editor"

    # Check if symlink exists
    if [[ ! -L "$editor_link" ]]; then
        if [[ -d "$editor_link" ]]; then
            log_error "Path exists but is not a symlink: $editor_link"
            return 2
        fi
        log_warn "Symlink does not exist: $editor_link"
        return 1
    fi

    # Check symlink target
    local actual_target="$(readlink "$editor_link")"
    if [[ "$actual_target" != "$expected_target" ]]; then
        log_warn "Symlink points to wrong target:"
        log_warn "  Expected: $expected_target"
        log_warn "  Actual: $actual_target"
        return 2
    fi

    # Check if target exists
    local target_path="$(cd "$(dirname "$editor_link")" && cd "$expected_target" 2>/dev/null && pwd)"
    if [[ ! -d "$target_path" ]]; then
        log_error "Symlink target does not exist: $target_path"
        return 1
    fi

    return 0
}

# Check symlinks for all enabled variants
symlink_check_all() {
    local repo_root="$(get_repo_root)"
    local variants=("main" "playtest" "demo")
    local all_valid=true
    local status_summary=""

    echo ""
    echo "Checking symlinks for all variants..."
    echo ""

    for variant in "${variants[@]}"; do
        local editor_link="$repo_root/variants/$variant/unity/Assets/Editor"

        if symlink_check "$variant" >/dev/null 2>&1; then
            status_summary+="  ✓ $variant: OK\n"
        else
            status_summary+="  ✗ $variant: BROKEN/MISSING\n"
            all_valid=false
        fi
    done

    echo -e "$status_summary"

    if $all_valid; then
        return 0
    else
        return 1
    fi
}

# Create symlink for a specific variant
symlink_create() {
    local variant="$1"
    local repo_root="$(get_repo_root)"
    local unity_project="$repo_root/variants/$variant/unity"
    local editor_link="$unity_project/Assets/Editor"
    local editor_source="../../../../src/Assets/Editor"

    log_info "Creating symlink for variant: $variant"

    # Create Assets directory if it doesn't exist
    mkdir -p "$unity_project/Assets"

    # Remove existing symlink or directory if it exists
    if [[ -e "$editor_link" || -L "$editor_link" ]]; then
        log_warn "Removing existing path: $editor_link"
        rm -rf "$editor_link"
    fi

    # Create symlink
    if ln -sf "$editor_source" "$editor_link"; then
        log_info "Created symlink: $editor_link -> $editor_source"
        return 0
    else
        log_error "Failed to create symlink: $editor_link"
        return 1
    fi
}

# Create symlinks for all variants
symlink_create_all() {
    local variants=("main" "playtest" "demo")
    local failed=false

    echo ""
    echo "Creating symlinks for all variants..."
    echo ""

    for variant in "${variants[@]}"; do
        if ! symlink_create "$variant"; then
            failed=true
        fi
    done

    if $failed; then
        return 1
    fi

    echo ""
    echo "All symlinks created successfully"
    return 0
}

# Remove symlink for a specific variant
symlink_remove() {
    local variant="$1"
    local repo_root="$(get_repo_root)"
    local editor_link="$repo_root/variants/$variant/unity/Assets/Editor"

    if [[ -L "$editor_link" ]]; then
        log_info "Removing symlink: $editor_link"
        rm "$editor_link"
        return 0
    elif [[ -e "$editor_link" ]]; then
        log_warn "Path exists but is not a symlink: $editor_link"
        log_warn "Use 'rm -rf' manually if you want to remove it"
        return 1
    else
        log_info "Symlink does not exist: $editor_link"
        return 0
    fi
}

# Remove symlinks for all variants
symlink_remove_all() {
    local variants=("main" "playtest" "demo")

    echo ""
    echo "Removing symlinks for all variants..."
    echo ""

    for variant in "${variants[@]}"; do
        symlink_remove "$variant"
    done

    echo ""
    echo "Symlink removal complete"
    return 0
}

# Repair symlink for a specific variant
symlink_repair() {
    local variant="$1"
    local repo_root="$(get_repo_root)"
    local editor_link="$repo_root/variants/$variant/unity/Assets/Editor"

    log_info "Repairing symlink for variant: $variant"

    # Remove if exists (symlink or directory)
    if [[ -e "$editor_link" || -L "$editor_link" ]]; then
        log_info "Removing existing path: $editor_link"
        rm -rf "$editor_link"
    fi

    # Recreate
    symlink_create "$variant"
}

# Repair symlinks for all variants
symlink_repair_all() {
    local variants=("main" "playtest" "demo")
    local failed=false

    echo ""
    echo "Repairing symlinks for all variants..."
    echo ""

    for variant in "${variants[@]}"; do
        if ! symlink_repair "$variant"; then
            failed=true
        fi
    done

    if $failed; then
        return 1
    fi

    echo ""
    echo "All symlinks repaired successfully"
    return 0
}

# Show detailed symlink status for all variants
symlink_status() {
    local repo_root="$(get_repo_root)"
    local variants=("main" "playtest" "demo")

    echo ""
    echo "=== Symlink Status ==="
    echo ""

    for variant in "${variants[@]}"; do
        local editor_link="$repo_root/variants/$variant/unity/Assets/Editor"
        local expected_target="../../../../src/Assets/Editor"

        echo "Variant: $variant"
        echo "  Link: $editor_link"

        if [[ -L "$editor_link" ]]; then
            local actual_target="$(readlink "$editor_link")"
            local target_path="$(cd "$(dirname "$editor_link")" 2>/dev/null && cd "$actual_target" 2>/dev/null && pwd)"

            echo "  Type: Symlink"
            echo "  Target: $actual_target"

            if [[ "$actual_target" == "$expected_target" ]]; then
                echo "  Target Check: ✓ Correct"
            else
                echo "  Target Check: ✗ Wrong (expected: $expected_target)"
            fi

            if [[ -d "$target_path" ]]; then
                echo "  Resolution: ✓ Valid (points to: $target_path)"
            else
                echo "  Resolution: ✗ Broken (target not found)"
            fi
        elif [[ -d "$editor_link" ]]; then
            echo "  Type: Directory (should be symlink!)"
            echo "  Status: ✗ Wrong type"
        elif [[ -e "$editor_link" ]]; then
            echo "  Type: File (should be symlink!)"
            echo "  Status: ✗ Wrong type"
        else
            echo "  Type: Missing"
            echo "  Status: ✗ Not found"
        fi

        echo ""
    done
}

# Validate symlink exists and points to correct location
symlink_validate() {
    local variant="$1"
    local repo_root="$(get_repo_root)"
    local editor_link="$repo_root/variants/$variant/unity/Assets/Editor"
    local expected_target="../../../../src/Assets/Editor"

    if [[ ! -L "$editor_link" ]]; then
        return 1  # Not a symlink
    fi

    local actual_target="$(readlink "$editor_link")"
    [[ "$actual_target" == "$expected_target" ]]
}
