#!/usr/bin/env bash
# lib/modules/steamcmd.sh - SteamCMD operations

# Module initialization
STEAMCMD_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$STEAMCMD_MODULE_DIR/../core/logger.sh"
source "$STEAMCMD_MODULE_DIR/../core/errors.sh"
source "$STEAMCMD_MODULE_DIR/../core/config.sh"

# Check if SteamCMD is installed
steamcmd_check_installed() {
    if ! command_exists steamcmd; then
        log_error "SteamCMD not installed"
        echo ""
        echo "Install with: brew install steamcmd"
        return $ERROR_DEPENDENCY
    fi
    return 0
}

# Check if game is actually downloaded (regardless of manifest state)
steamcmd_is_game_present() {
    local install_dir="${1:-$(config_get paths.game_files)}"

    # Check for Erenshor-specific files
    if [[ -f "$install_dir/Erenshor.exe" && -d "$install_dir/Erenshor_Data" ]]; then
        return 0
    fi

    return 1
}

# Get current installed build ID
steamcmd_get_current_build() {
    local install_dir="${1:-$(config_get paths.game_files)}"

    # First, check if game files actually exist
    if ! steamcmd_is_game_present "$install_dir"; then
        log_debug "Game files not found in: $install_dir"
        echo "0"
        return
    fi

    # Try to detect app_id from manifest files
    local app_id=""
    if [[ -d "$install_dir/steamapps" ]]; then
        local manifest=$(ls "$install_dir/steamapps"/appmanifest_*.acf 2>/dev/null | head -1)
        if [[ -n "$manifest" ]]; then
            app_id=$(basename "$manifest" | grep -o '[0-9]\+')
        fi
    fi

    # Fallback to config if not found
    if [[ -z "$app_id" ]]; then
        app_id=$(config_get steam.app_id)
    fi

    # SteamCMD creates manifest in steamapps subdirectory
    local manifest_file="$install_dir/steamapps/appmanifest_${app_id}.acf"

    if [[ ! -f "$manifest_file" ]]; then
        log_debug "Manifest not found: $manifest_file"
        # Game exists but no manifest - likely manual download
        echo "manual"
        return
    fi

    # Extract build ID from manifest
    # The manifest format is: "buildid"		"20287268"
    local build_id=$(grep '"buildid"' "$manifest_file" | head -1 | grep -o '[0-9]\+' || echo "0")

    # If buildid is 0, check for TargetBuildID (incomplete download)
    if [[ "$build_id" == "0" ]]; then
        local target_build_id=$(grep '"TargetBuildID"' "$manifest_file" | head -1 | grep -o '[0-9]\+' || echo "0")
        if [[ "$target_build_id" != "0" ]]; then
            log_debug "Using TargetBuildID from incomplete download: $target_build_id"
            echo "$target_build_id"
            return
        fi
        log_debug "Failed to extract build ID from manifest"
        # Game exists but build ID is 0 - likely incomplete/manual download
        echo "manual"
        return
    fi

    echo "$build_id"
}

# Check for updates (returns 0 if update available)
steamcmd_check_update() {
    local install_dir="${1:-$(config_get paths.game_files)}"

    log_info "Checking for game updates..."

    local current_build=$(steamcmd_get_current_build "$install_dir")
    log_debug "Current build: $current_build"

    if [[ "$current_build" == "0" ]]; then
        log_info "Game not installed"
        return 0  # Update available (needs initial download)
    fi

    # For now, we'll rely on SteamCMD validate to check
    # A proper check would query Steam API, but that requires more setup
    log_info "Current build: $current_build"
    return 0
}

# Download game via SteamCMD
# Usage: steamcmd_download [app_id] [install_dir] [variant]
steamcmd_download() {
    local app_id="${1:-$(config_get steam.app_id)}"
    local install_dir="${2:-$(config_get paths.game_files)}"
    local variant="${3:-main}"

    log_info "Starting game download..."
    log_debug "App ID: $app_id"
    log_debug "Install dir: $install_dir"
    log_debug "Variant: $variant"

    # Get platform and username from global config (applies to all variants)
    local platform=$(config_get global.steam.platform "windows")
    local username=$(config_get global.steam.username "")

    # Ensure install directory exists
    mkdir -p "$install_dir"

    # Prompt for username if not configured
    if [[ -z "$username" ]]; then
        echo ""
        username=$(prompt "Steam username" "anonymous")
    fi

    # Build SteamCMD command
    local cmd=(
        steamcmd
        "+@sSteamCmdForcePlatformType" "$platform"
        "+force_install_dir" "$install_dir"
        "+login" "$username"
        "+app_update" "$app_id" "validate"
        "+quit"
    )

    log_debug "Executing SteamCMD: ${cmd[*]}"

    # Execute with output capture
    if "${cmd[@]}"; then
        log_info "Download complete"
        local new_build=$(steamcmd_get_current_build "$install_dir")
        log_info "Build ID: $new_build"
        return 0
    else
        local exit_code=$?
        log_error "SteamCMD failed with exit code: $exit_code"
        return $ERROR_PROCESS
    fi
}

# Get game directory size
steamcmd_get_game_size() {
    local install_dir="${1:-$(config_get paths.game_files)}"

    if [[ ! -d "$install_dir" ]]; then
        echo "0"
        return
    fi

    du -sm "$install_dir" | cut -f1
}

# Clean up incomplete SteamCMD downloads
steamcmd_clean_incomplete() {
    local install_dir="${1:-$(config_get paths.game_files)}"
    local downloading_dir="$install_dir/steamapps/downloading"

    if [[ -d "$downloading_dir" ]]; then
        log_info "Cleaning incomplete download artifacts..."
        local size=$(du -sh "$downloading_dir" 2>/dev/null | cut -f1)
        log_info "Removing $size from: $downloading_dir"
        rm -rf "$downloading_dir"
        log_info "Cleanup complete"
        return 0
    fi

    log_debug "No incomplete downloads to clean"
    return 0
}
