#!/usr/bin/env bash
# lib/modules/steamcmd.sh - SteamCMD operations

# Guard against multiple sourcing
[[ -n "${STEAMCMD_MODULE_LOADED:-}" ]] && return 0
readonly STEAMCMD_MODULE_LOADED=1

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
# Usage: steamcmd_download [app_id] [install_dir] [variant] [validate]
# Parameters:
#   app_id      - Steam App ID to download
#   install_dir - Installation directory path
#   variant     - Game variant (main, playtest, demo)
#   validate    - Optional: "true" to enable full file validation (default: "false")
steamcmd_download() {
    local app_id="${1:-$(config_get steam.app_id)}"
    local install_dir="${2:-$(config_get paths.game_files)}"
    local variant="${3:-main}"
    local validate="${4:-false}"

    log_info "Starting game download..."
    log_debug "App ID: $app_id"
    log_debug "Install dir: $install_dir"
    log_debug "Variant: $variant"
    log_debug "Validate: $validate"

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

    # Build SteamCMD command conditionally based on validate flag
    local cmd=(
        steamcmd
        "+@sSteamCmdForcePlatformType" "$platform"
        "+force_install_dir" "$install_dir"
        "+login" "$username"
    )

    # Add app_update with or without validate flag
    if [[ "$validate" == "true" ]]; then
        log_info "Running with full file validation (all files will be verified)"
        cmd+=("+app_update" "$app_id" "validate")
    else
        log_info "Running incremental update (only changed files will be downloaded)"
        cmd+=("+app_update" "$app_id")
    fi

    cmd+=("+quit")

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

# Get build timestamp from Steam
# Returns ISO 8601 formatted timestamp, or empty string if unavailable
steamcmd_get_build_timestamp() {
    local app_id="${1:-$(config_get steam.app_id)}"
    local branch="${2:-public}"

    if [[ -z "$branch" ]]; then
        log_debug "Invalid branch parameter (empty)"
        echo ""
        return
    fi

    log_debug "Fetching build timestamp for app $app_id, branch $branch"

    # Check if steamcmd is available
    if ! command_exists steamcmd; then
        log_debug "SteamCMD not available"
        echo ""
        return
    fi

    # Use SteamCMD to get app info
    local app_info=$(steamcmd \
        "+login anonymous" \
        "+app_info_print $app_id" \
        "+quit" 2>/dev/null)

    if [[ -z "$app_info" ]]; then
        log_debug "Failed to fetch app info from Steam"
        echo ""
        return
    fi

    # Extract timeupdated from the specified branch
    # Format: "timeupdated"		"1728523943"
    local timestamp_unix=$(echo "$app_info" | \
        grep -A 50 "\"branches\"" | \
        grep -A 10 "\"$branch\"" | \
        grep '"timeupdated"' | \
        head -1 | \
        grep -o '[0-9]\+' || echo "")

    if [[ -z "$timestamp_unix" ]]; then
        log_debug "Could not extract build timestamp from Steam"
        echo ""
        return
    fi

    # Convert Unix timestamp to ISO 8601 format
    if command -v date >/dev/null 2>&1; then
        # macOS uses -r for Unix timestamp, Linux uses -d
        if date -r "$timestamp_unix" -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null; then
            return
        elif date -d "@$timestamp_unix" -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null; then
            return
        fi
    fi

    # Fallback - return empty string
    log_debug "Could not convert timestamp to ISO 8601 format"
    echo ""
}

# Get download size from Steam
# Returns compressed download size in bytes, or empty string if unavailable
steamcmd_get_download_size() {
    local app_id="${1:-$(config_get steam.app_id)}"
    local branch="${2:-public}"

    if [[ -z "$branch" ]]; then
        log_debug "Invalid branch parameter (empty)"
        echo ""
        return
    fi

    log_debug "Fetching download size for app $app_id, branch $branch"

    # Check if steamcmd is available
    if ! command_exists steamcmd; then
        log_debug "SteamCMD not available"
        echo ""
        return
    fi

    # Use SteamCMD to get app info
    local app_info=$(steamcmd \
        "+login anonymous" \
        "+app_info_print $app_id" \
        "+quit" 2>/dev/null)

    if [[ -z "$app_info" ]]; then
        log_debug "Failed to fetch app info from Steam"
        echo ""
        return
    fi

    # Extract download size from depots
    # The structure is:
    #   "depots"
    #   {
    #       "2382521"  // Main depot (first depot typically)
    #       {
    #           "manifests"
    #           {
    #               "public"
    #               {
    #                   "download"  "2465185200"  // Compressed download size
    #               }
    #           }
    #       }
    #   }

    # Find the depots section, then find the first depot with manifests for our branch
    local download_size=$(echo "$app_info" | \
        grep -A 200 "\"depots\"" | \
        grep -A 100 "\"manifests\"" | \
        grep -A 10 "\"$branch\"" | \
        grep '"download"' | \
        head -1 | \
        grep -o '[0-9]\+' || echo "")

    if [[ -z "$download_size" ]]; then
        log_debug "Could not extract download size from Steam"
        echo ""
        return
    fi

    echo "$download_size"
}

# Get manifest ID for current build
steamcmd_get_manifest_id() {
    local install_dir="${1:-$(config_get paths.game_files)}"
    local app_id="${2:-$(config_get steam.app_id)}"

    local manifest_file="$install_dir/steamapps/appmanifest_${app_id}.acf"

    if [[ ! -f "$manifest_file" ]]; then
        echo ""
        return
    fi

    # Extract manifest ID
    # Format: "manifest"		"8701699651234567890"
    local manifest_id=$(grep '"manifest"' "$manifest_file" | head -1 | grep -o '[0-9]\+' || echo "")
    echo "$manifest_id"
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
