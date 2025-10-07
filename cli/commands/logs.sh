#!/usr/bin/env bash
# commands/logs.sh - View logs

command_main() {
    local module="${1:-}"
    local tail_lines=50
    local follow=false

    # Parse options
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                show_logs_help
                exit 0
                ;;
            --tail)
                # --tail can have an optional argument
                if [[ -n "${2:-}" && "$2" =~ ^[0-9]+$ ]]; then
                    tail_lines="$2"
                    shift 2
                else
                    tail_lines=50
                    shift
                fi
                ;;
            --follow|-f)
                follow=true
                shift
                ;;
            --lines|-n)
                tail_lines="$2"
                shift 2
                ;;
            *)
                module="$1"
                shift
                ;;
        esac
    done

    local logs_dir=$(config_get paths.logs)

    if [[ ! -d "$logs_dir" ]]; then
        error "Logs directory not found: $logs_dir"
        exit 1
    fi

    # Show specific module or main log
    if [[ -n "$module" ]]; then
        local log_file=$(log_get_latest "$module")

        if [[ -z "$log_file" ]]; then
            error "No logs found for module: $module"
            exit 1
        fi

        show_log_file "$log_file" "$tail_lines" "$follow"
    else
        # Show main log
        local main_log="$logs_dir/erenshor.log"

        if [[ ! -f "$main_log" ]]; then
            error "Main log not found: $main_log"
            exit 1
        fi

        show_log_file "$main_log" "$tail_lines" "$follow"
    fi
}

show_log_file() {
    local log_file="$1"
    local tail_lines="$2"
    local follow="$3"

    echo ""
    info "Log file: $log_file"
    echo ""

    if [[ "$follow" == true ]]; then
        tail -f "$log_file"
    else
        tail -n "$tail_lines" "$log_file"
    fi
}

show_logs_help() {
    cat << 'EOF'
erenshor logs - View automation logs

USAGE:
    erenshor logs [MODULE] [OPTIONS]

DESCRIPTION:
    View logs from the automation pipeline. Shows main log by default,
    or module-specific logs if a module name is provided.

OPTIONS:
    --tail              Show last 50 lines (default)
    -f, --follow        Follow log output (like tail -f)
    -n, --lines N       Show last N lines
    -h, --help          Show this help message

MODULES:
    update              Update pipeline logs
    download            SteamCMD download logs
    extract             AssetRipper extraction logs
    export              Unity export logs
    deploy              Database deployment logs

EXAMPLES:
    # View main log
    erenshor logs

    # View update module logs
    erenshor logs update

    # Show last 100 lines
    erenshor logs --lines 100

    # Follow logs in real-time
    erenshor logs --follow

SEE ALSO:
    erenshor status     Show system status
    erenshor doctor     Diagnose issues
EOF
}
