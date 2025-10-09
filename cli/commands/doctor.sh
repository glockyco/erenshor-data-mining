#!/usr/bin/env bash
# commands/doctor.sh - Diagnose system issues

command_main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_doctor_help
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                echo "Use 'erenshor doctor --help' for usage."
                exit 1
                ;;
        esac
    done

    local errors=0
    local warnings=0

    echo ""
    bold "=== Erenshor Pipeline Diagnostics ==="
    echo ""

    # Check system requirements
    echo "$(bold "System Requirements:")"

    # Check OS
    if [[ "$(uname)" == "Darwin" ]]; then
        success "macOS detected ($(sw_vers -productVersion))"
    else
        error "Not running on macOS"
        ((errors++))
    fi

    # Check bash version
    if [[ "${BASH_VERSINFO[0]}" -ge 4 ]]; then
        success "Bash ${BASH_VERSION}"
    else
        error "Bash version too old: ${BASH_VERSION} (need 4.0+)"
        ((errors++))
    fi

    # Check disk space
    local available_mb=$(disk_space_available .)
    if [[ $available_mb -gt 10000 ]]; then
        success "Disk space: ${available_mb}MB available"
    else
        warning "Low disk space: ${available_mb}MB available (recommend 10GB+)"
        ((warnings++))
    fi

    echo ""

    # Check dependencies
    echo "$(bold "Dependencies:")"

    check_dependency "Unity" "$(config_get unity.path)" true || ((errors++))
    check_dependency "SteamCMD" "steamcmd" true || ((errors++))
    check_dependency "AssetRipper" "$(config_get assetripper.path)" false || ((warnings++))
    check_dependency "SQLite" "sqlite3" true || ((errors++))
    check_dependency "jq" "jq" false || ((warnings++))

    echo ""

    # Check configuration
    echo "$(bold "Configuration:")"

    if [[ -f "$ERENSHOR_CONFIG" ]]; then
        success "Config file exists: $ERENSHOR_CONFIG"

        # Validate config
        if config_validate 2>/dev/null; then
            success "Configuration valid"
        else
            error "Configuration has errors"
            ((errors++))
        fi
    else
        warning "Config file not found (will use defaults)"
        ((warnings++))
    fi

    echo ""

    # Check projects
    echo "$(bold "Projects:")"

    local unity_project=$(config_get paths.unity_project)
    if [[ -d "$unity_project" ]]; then
        success "Unity project: $unity_project"

        # Check for Editor scripts in src/
        local repo_root="$(cd "$unity_project/../../.." && pwd)"
        if [[ -d "$repo_root/src/Assets/Editor" ]]; then
            success "Editor scripts found"
        else
            warning "Editor scripts not found in src/Assets/Editor"
            ((warnings++))
        fi

        # Check for export script
        if [[ -f "$unity_project/export.sh" ]]; then
            success "Export script found"
        elif [[ -f "$repo_root/export.sh" ]]; then
            warning "Export script not copied to Unity project"
            info "Run: erenshor export (will auto-copy on first run)"
            ((warnings++))
        else
            error "Export script not found: $repo_root/export.sh"
            ((errors++))
        fi

        # Check for NuGet packages
        if [[ -d "$unity_project/Assets/Packages" ]]; then
            success "NuGet packages found"
        else
            error "NuGet packages missing (required for Unity compilation)"
            info "Run: erenshor extract (will auto-copy packages)"
            ((errors++))
        fi

        # Check for NuGet config files
        if [[ -f "$unity_project/Assets/NuGet.config" && -f "$unity_project/Assets/packages.config" ]]; then
            success "NuGet config files found"
        else
            warning "NuGet config files missing"
            ((warnings++))
        fi
    else
        error "Unity project not found: $unity_project"
        ((errors++))
    fi

    local wiki_project=$(config_get paths.wiki_project)
    if [[ -d "$wiki_project" ]]; then
        success "Wiki project: $wiki_project"
    else
        warning "Wiki project not found: $wiki_project"
        ((warnings++))
    fi

    echo ""

    # Check permissions
    echo "$(bold "Permissions:")"

    local logs_dir=$(config_get paths.logs)
    if [[ -w "$(dirname "$logs_dir")" ]] || [[ -w "$logs_dir" ]]; then
        success "Can write to logs directory"
    else
        error "Cannot write to logs directory: $logs_dir"
        ((errors++))
    fi

    local output_dir=$(config_get paths.output)
    if [[ -w "$(dirname "$output_dir")" ]] || [[ -w "$output_dir" ]]; then
        success "Can write to output directory"
    else
        error "Cannot write to output directory: $output_dir"
        ((errors++))
    fi

    echo ""

    # Check symlinks
    echo "$(bold "Symlinks:")"

    local symlink_errors=0
    local repo_root="$(cd "$ERENSHOR_CLI_ROOT/.." && pwd)"

    for variant in "${ERENSHOR_VARIANTS[@]}"; do
        local variant_dir="$repo_root/variants/$variant/unity"

        # Skip check if variant directory doesn't exist yet
        if [[ ! -d "$variant_dir" ]]; then
            info "Variant directory not yet created: $variant (OK - will be created on extract)"
            continue
        fi

        if symlink_check "$variant" >/dev/null 2>&1; then
            success "Symlink valid for $variant"
        else
            warning "Symlink broken/missing for $variant"
            ((warnings++))
        fi
    done

    echo ""

    # Summary
    echo "$(bold "Summary:")"
    echo "Errors: $errors"
    echo "Warnings: $warnings"
    echo ""

    if [[ $errors -eq 0 && $warnings -eq 0 ]]; then
        celebrate "All checks passed! System is healthy."
        return 0
    elif [[ $errors -eq 0 ]]; then
        warning "System is functional but has warnings"
        return 0
    else
        error "System has critical errors that need attention"
        echo ""
        echo "$(bold "Recommendations:")"
        echo "  1. Fix the errors listed above"
        echo "  2. Run 'erenshor doctor' again to verify"
        echo "  3. Check documentation: ~/.erenshor/docs/"
        return 1
    fi
}

check_dependency() {
    local name="$1"
    local cmd="$2"
    local required="${3:-true}"

    if [[ -x "$cmd" ]] || command_exists "$cmd"; then
        if [[ -x "$cmd" ]]; then
            success "$name: $cmd"
        else
            success "$name: $(which "$cmd")"
        fi
        return 0
    else
        if [[ "$required" == true ]]; then
            error "$name: not found (required)"
            return 1
        else
            warning "$name: not found (optional)"
            return 1
        fi
    fi
}

show_doctor_help() {
    cat << 'EOF'
erenshor doctor - Diagnose system issues

USAGE:
    erenshor doctor

DESCRIPTION:
    Runs a comprehensive diagnostic check of your Erenshor automation setup.
    Checks dependencies, configuration, project structure, and permissions.

CHECKS:
    - System requirements (OS, Bash version, disk space)
    - Dependencies (Unity, SteamCMD, SQLite, etc.)
    - Configuration file validity
    - Project structure (Unity project, wiki project)
    - File permissions

EXIT STATUS:
    0   All checks passed or only warnings
    1   Critical errors detected

EXAMPLES:
    # Run diagnostics
    erenshor doctor

SEE ALSO:
    erenshor status     Show current system status
    erenshor config     Manage configuration
EOF
}
