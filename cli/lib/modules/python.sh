#!/usr/bin/env bash
# lib/modules/python.sh - Python CLI integration

# Guard against multiple sourcing
[[ -n "${PYTHON_MODULE_LOADED:-}" ]] && return 0
readonly PYTHON_MODULE_LOADED=1

# Module initialization
PYTHON_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PYTHON_MODULE_DIR/../core/logger.sh"
source "$PYTHON_MODULE_DIR/../core/errors.sh"
source "$PYTHON_MODULE_DIR/../core/config.sh"
source "$PYTHON_MODULE_DIR/../core/utils.sh"
source "$PYTHON_MODULE_DIR/../core/variants.sh"

# Python environment detection
readonly PYTHON_PACKAGE="erenshor"
readonly PYTHON_CLI_MODULE="erenshor.cli.main"

# Check if uv is available
python_has_uv() {
    command_exists uv
}

# Check if Python 3 is available
python_has_python3() {
    command_exists python3
}

# Get Python executable path
python_get_executable() {
    if python_has_uv; then
        echo "uv run python"
    elif python_has_python3; then
        echo "python3"
    else
        return 1
    fi
}

# Check if Python environment is ready
python_check_env() {
    log_debug "Checking Python environment..."

    # Check for Python 3
    if ! python_has_python3; then
        log_error "Python 3 not found. Please install Python 3.10 or higher."
        return $ERROR_DEPENDENCY
    fi

    local python_version
    python_version=$(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
    log_debug "Python version: $python_version"

    # Check for uv (preferred)
    if python_has_uv; then
        local uv_version
        uv_version=$(uv --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        log_debug "uv version: $uv_version"
        log_debug "Using uv for Python environment management"
        return 0
    fi

    # Check if package is installed in standard Python
    if python3 -c "import $PYTHON_PACKAGE" 2>/dev/null; then
        log_debug "Python package '$PYTHON_PACKAGE' is installed"
        return 0
    fi

    log_error "Python environment not ready. Install 'uv' or run: pip install -e src/"
    return $ERROR_DEPENDENCY
}

# Execute Python CLI command
# Usage: python_exec <args...>
# Example: python_exec wiki fetch --entity items
python_exec() {
    log_debug "Executing Python CLI: $*"

    # Check environment first
    if ! python_check_env; then
        return $?
    fi

    # Build command
    local cmd
    if python_has_uv; then
        # Use uv run to execute in managed environment
        cmd=(uv run python -m "$PYTHON_CLI_MODULE" "$@")
    else
        # Use system Python
        cmd=(python3 -m "$PYTHON_CLI_MODULE" "$@")
    fi

    # Execute command and capture exit code
    log_debug "Running: ${cmd[*]}"
    "${cmd[@]}"
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        log_debug "Python CLI exited with code: $exit_code"
    fi

    return $exit_code
}

# Execute Python CLI command with config override
# Usage: python_exec_with_config <config_key> <config_value> <args...>
python_exec_with_config() {
    local config_key="$1"
    local config_value="$2"
    shift 2

    # Set environment variable for config override
    # The Python CLI should respect ERENSHOR_* environment variables
    local env_var="ERENSHOR_${config_key^^}"
    env_var="${env_var//./_}"  # Replace dots with underscores

    log_debug "Setting config override: $env_var=$config_value"
    declare -x "$env_var=$config_value"

    # Execute command
    python_exec "$@"
    local exit_code=$?

    # Clean up environment
    unset "$env_var"

    return $exit_code
}

# Execute Python CLI command with variant context
# Usage: python_exec_variant <variant> <args...>
python_exec_variant() {
    local variant="$1"
    shift

    # Validate variant before passing to Python
    if ! variant_validate "$variant"; then
        log_error "Invalid variant: $variant"
        return $ERROR_ARGS
    fi

    log_debug "Executing Python CLI for variant: $variant"

    # Pass variant as argument to Python CLI
    python_exec --variant "$variant" "$@"
}

# Check if Python CLI command exists
# Usage: python_has_command <command>
# Example: python_has_command wiki fetch
python_has_command() {
    local command="$*"

    if ! python_check_env; then
        return 1
    fi

    # Try to get help for the command
    if python_exec $command --help &>/dev/null; then
        return 0
    fi

    return 1
}

# Get Python CLI version
python_get_cli_version() {
    if ! python_check_env; then
        return 1
    fi

    python_exec --version 2>&1 | head -1
}

# Install Python dependencies
python_install_deps() {
    log_info "Installing Python dependencies..."

    local repo_root
    repo_root=$(config_get paths.repo_root)

    if python_has_uv; then
        log_info "Using uv to install dependencies"
        cd "$repo_root" && uv sync --dev
    else
        log_info "Using pip to install package in editable mode"
        python3 -m pip install -e "$repo_root/src/" --quiet
    fi

    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        log_info "Python dependencies installed successfully"
    else
        log_error "Failed to install Python dependencies"
    fi

    return $exit_code
}

# Run Python tests
python_run_tests() {
    log_info "Running Python test suite..."

    local repo_root
    repo_root=$(config_get paths.repo_root)

    if python_has_uv; then
        cd "$repo_root" && uv run pytest "$@"
    else
        cd "$repo_root" && python3 -m pytest "$@"
    fi

    return $?
}

# Show Python environment info
python_show_env() {
    echo "Python Environment:"
    echo "  Python 3: $(python_has_python3 && echo "✓" || echo "✗")"

    if python_has_python3; then
        local py_version
        py_version=$(python3 --version 2>&1)
        echo "  Version: $py_version"
    fi

    echo "  uv: $(python_has_uv && echo "✓" || echo "✗")"

    if python_has_uv; then
        local uv_version
        uv_version=$(uv --version 2>&1)
        echo "  Version: $uv_version"
    fi

    echo "  Package: $(python3 -c "import $PYTHON_PACKAGE; print('✓')" 2>/dev/null || echo "✗")"

    if python3 -c "import $PYTHON_PACKAGE" 2>/dev/null; then
        local pkg_version
        pkg_version=$(python3 -c "import $PYTHON_PACKAGE; print(getattr($PYTHON_PACKAGE, '__version__', 'unknown'))" 2>/dev/null)
        echo "  Version: $pkg_version"
    fi

    echo "  CLI: $(python_check_env &>/dev/null && echo "✓" || echo "✗")"
}

# Validate Python integration
python_validate() {
    log_info "Validating Python integration..."

    local errors=0

    # Check Python 3
    if ! python_has_python3; then
        log_error "Python 3 not found"
        ((errors++))
    else
        log_info "✓ Python 3 found"
    fi

    # Check uv (optional but recommended)
    if ! python_has_uv; then
        log_warn "uv not found (recommended for dependency management)"
    else
        log_info "✓ uv found"
    fi

    # Check Python environment
    if ! python_check_env; then
        log_error "Python environment not ready"
        ((errors++))
    else
        log_info "✓ Python environment ready"
    fi

    # Check Python CLI
    if ! python_exec --help &>/dev/null; then
        log_error "Python CLI not working"
        ((errors++))
    else
        log_info "✓ Python CLI working"
    fi

    if [[ $errors -gt 0 ]]; then
        log_error "Python integration validation failed with $errors error(s)"
        return 1
    fi

    log_info "Python integration validated successfully"
    return 0
}
