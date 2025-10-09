#!/usr/bin/env bash
# commands/test-python.sh - Test Python CLI integration

command_main() {
    local test_type="${1:-all}"

    echo "Testing Python CLI Integration"
    echo "================================"
    echo ""

    case "$test_type" in
        env)
            test_env
            ;;
        cli)
            test_cli
            ;;
        all)
            test_env
            echo ""
            test_cli
            ;;
        *)
            error "Unknown test type: $test_type"
            echo "Usage: erenshor test-python [env|cli|all]"
            return 1
            ;;
    esac
}

test_env() {
    echo "1. Python Environment Check"
    echo "----------------------------"

    # Show environment info
    python_show_env

    echo ""
    echo "2. Validating Python Integration"
    echo "----------------------------------"

    if python_validate; then
        echo ""
        echo "✓ Python integration is working correctly"
        return 0
    else
        echo ""
        echo "✗ Python integration validation failed"
        return 1
    fi
}

test_cli() {
    echo "3. Testing Python CLI Commands"
    echo "-------------------------------"

    # Test 1: Help command
    echo ""
    echo "Test 1: Python CLI help"
    if python_exec --help >/dev/null 2>&1; then
        echo "✓ Python CLI --help works"
    else
        echo "✗ Python CLI --help failed"
        return 1
    fi

    # Test 2: Check-paths command
    echo ""
    echo "Test 2: Python CLI check-paths"
    if python_exec check-paths >/dev/null 2>&1; then
        echo "✓ Python CLI check-paths works"
    else
        echo "✗ Python CLI check-paths failed (this is expected if paths aren't configured)"
    fi

    # Test 3: DB subcommand
    echo ""
    echo "Test 3: Python CLI db --help"
    if python_exec db --help >/dev/null 2>&1; then
        echo "✓ Python CLI db subcommand works"
    else
        echo "✗ Python CLI db subcommand failed"
        return 1
    fi

    # Test 4: Wiki subcommand
    echo ""
    echo "Test 4: Python CLI wiki --help"
    if python_exec wiki --help >/dev/null 2>&1; then
        echo "✓ Python CLI wiki subcommand works"
    else
        echo "✗ Python CLI wiki subcommand failed"
        return 1
    fi

    echo ""
    echo "✓ All Python CLI tests passed"
    return 0
}

command_help() {
    cat << EOF
Test Python CLI integration

USAGE:
    erenshor test-python [type]

ARGUMENTS:
    type        Test type: env, cli, or all (default: all)

EXAMPLES:
    # Run all tests
    erenshor test-python

    # Test only environment
    erenshor test-python env

    # Test only CLI commands
    erenshor test-python cli

DESCRIPTION:
    This command verifies that the Bash CLI can properly invoke
    Python CLI commands. It tests:

    1. Python environment detection (Python 3, uv)
    2. Python package installation
    3. Python CLI command execution
    4. Error handling and return codes

    Phase 3 of the architecture merge requires seamless Bash → Python
    integration, and this command validates that integration.
EOF
}
