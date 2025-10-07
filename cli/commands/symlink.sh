#!/usr/bin/env bash
# commands/symlink.sh - Manage symlinks for variant Unity projects

# Source symlink module
SYMLINK_CMD_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SYMLINK_CMD_DIR/../lib/core/symlinks.sh"

# Command entry point
command_main() {
    local subcommand="${1:-status}"
    local variant=""
    local all_variants=false

    # Remove subcommand from args
    if [[ $# -gt 0 ]]; then
        shift
    fi

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -v|--variant)
                variant="$2"
                shift 2
                ;;
            -a|--all-variants)
                all_variants=true
                shift
                ;;
            -h|--help)
                show_symlink_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor symlink --help' for usage."
                exit 1
                ;;
        esac
    done

    # Route to subcommand
    case "$subcommand" in
        check)
            symlink_check_command "$variant" "$all_variants"
            ;;
        create)
            symlink_create_command "$variant" "$all_variants"
            ;;
        remove)
            symlink_remove_command "$variant" "$all_variants"
            ;;
        repair)
            symlink_repair_command "$variant" "$all_variants"
            ;;
        status)
            symlink_status_command "$variant" "$all_variants"
            ;;
        -h|--help|help)
            show_symlink_help
            exit 0
            ;;
        *)
            error "Unknown symlink subcommand: $subcommand"
            echo ""
            echo "Use 'erenshor symlink --help' for usage."
            exit 1
            ;;
    esac
}

# Check symlinks
symlink_check_command() {
    local variant="$1"
    local all_variants="$2"

    if [[ "$all_variants" == true ]]; then
        if symlink_check_all; then
            success "All symlinks are valid"
            exit 0
        else
            error "Some symlinks are broken or missing"
            echo ""
            echo "Run 'erenshor symlink repair' to fix them"
            exit 1
        fi
    elif [[ -n "$variant" ]]; then
        echo ""
        echo "Checking symlink for variant: $variant"
        echo ""
        if symlink_check "$variant"; then
            success "Symlink is valid"
            exit 0
        else
            error "Symlink is broken or missing"
            echo ""
            echo "Run 'erenshor symlink repair --variant $variant' to fix it"
            exit 1
        fi
    else
        symlink_check_all
        exit $?
    fi
}

# Create symlinks
symlink_create_command() {
    local variant="$1"
    local all_variants="$2"

    if [[ "$all_variants" == true ]]; then
        symlink_create_all
        exit $?
    elif [[ -n "$variant" ]]; then
        echo ""
        if symlink_create "$variant"; then
            success "Symlink created for variant: $variant"
            exit 0
        else
            error "Failed to create symlink for variant: $variant"
            exit 1
        fi
    else
        # Default to creating all
        symlink_create_all
        exit $?
    fi
}

# Remove symlinks
symlink_remove_command() {
    local variant="$1"
    local all_variants="$2"

    if [[ "$all_variants" == true ]]; then
        symlink_remove_all
        exit $?
    elif [[ -n "$variant" ]]; then
        echo ""
        if symlink_remove "$variant"; then
            success "Symlink removed for variant: $variant"
            exit 0
        else
            error "Failed to remove symlink for variant: $variant"
            exit 1
        fi
    else
        error "Specify a variant with --variant or use --all-variants"
        exit 1
    fi
}

# Repair symlinks
symlink_repair_command() {
    local variant="$1"
    local all_variants="$2"

    if [[ "$all_variants" == true ]]; then
        symlink_repair_all
        exit $?
    elif [[ -n "$variant" ]]; then
        echo ""
        if symlink_repair "$variant"; then
            success "Symlink repaired for variant: $variant"
            exit 0
        else
            error "Failed to repair symlink for variant: $variant"
            exit 1
        fi
    else
        # Default to repairing all
        symlink_repair_all
        exit $?
    fi
}

# Show symlink status
symlink_status_command() {
    local variant="$1"
    local all_variants="$2"

    if [[ -n "$variant" ]]; then
        # Show detailed status for single variant
        local repo_root="$(get_repo_root)"
        local editor_link="$repo_root/variants/$variant/unity/Assets/Editor"
        local expected_target="../../../../src/Assets/Editor"

        echo ""
        echo "=== Symlink Status: $variant ==="
        echo ""
        echo "Link: $editor_link"

        if [[ -L "$editor_link" ]]; then
            local actual_target="$(readlink "$editor_link")"
            local target_path="$(cd "$(dirname "$editor_link")" 2>/dev/null && cd "$actual_target" 2>/dev/null && pwd)"

            echo "Type: Symlink"
            echo "Target: $actual_target"

            if [[ "$actual_target" == "$expected_target" ]]; then
                success "Target Check: Correct"
            else
                error "Target Check: Wrong (expected: $expected_target)"
            fi

            if [[ -d "$target_path" ]]; then
                success "Resolution: Valid (points to: $target_path)"
            else
                error "Resolution: Broken (target not found)"
            fi
        elif [[ -d "$editor_link" ]]; then
            warning "Type: Directory (should be symlink!)"
        elif [[ -e "$editor_link" ]]; then
            warning "Type: File (should be symlink!)"
        else
            warning "Type: Missing"
        fi

        echo ""
    else
        # Show status for all variants
        symlink_status
    fi
}

# Show help
show_symlink_help() {
    cat << 'EOF'
erenshor symlink - Manage symlinks for variant Unity projects

USAGE:
    erenshor symlink <subcommand> [OPTIONS]

SUBCOMMANDS:
    check       Check if symlinks are valid
    create      Create missing symlinks
    remove      Remove symlinks
    repair      Repair broken symlinks
    status      Show detailed symlink status (default)

OPTIONS:
    -v, --variant NAME      Target specific variant (main, playtest, demo)
    -a, --all-variants      Target all variants
    -h, --help              Show this help message

DESCRIPTION:
    Manages symlinks between variant Unity projects and the shared Editor scripts.
    Each variant has a Unity project at variants/<variant>/unity/ with a symlink
    at Assets/Editor pointing to the shared src/Assets/Editor/ directory.

EXAMPLES:
    # Check all symlinks
    erenshor symlink check

    # Create symlinks for all variants
    erenshor symlink create

    # Create symlink for specific variant
    erenshor symlink create --variant playtest

    # Repair broken symlinks
    erenshor symlink repair

    # Show detailed status
    erenshor symlink status

    # Remove symlink for specific variant
    erenshor symlink remove --variant demo

SYMLINK STRUCTURE:
    variants/main/unity/Assets/Editor -> ../../../../src/Assets/Editor
    variants/playtest/unity/Assets/Editor -> ../../../../src/Assets/Editor
    variants/demo/unity/Assets/Editor -> ../../../../src/Assets/Editor

SEE ALSO:
    erenshor extract     Extraction creates symlinks automatically
    erenshor doctor      Diagnose system including symlink health
EOF
}
