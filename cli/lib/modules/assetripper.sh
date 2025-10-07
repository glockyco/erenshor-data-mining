#!/usr/bin/env bash
# lib/modules/assetripper.sh - AssetRipper operations with web API

# Module initialization
ASSETRIPPER_MODULE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ASSETRIPPER_MODULE_DIR/../core/logger.sh"
source "$ASSETRIPPER_MODULE_DIR/../core/errors.sh"
source "$ASSETRIPPER_MODULE_DIR/../core/config.sh"

# AssetRipper server management
ASSETRIPPER_PID=""
ASSETRIPPER_LOG=""

# Get AssetRipper base URL
_assetripper_get_url() {
    local port=$(config_get assetripper.port)
    echo "http://localhost:${port}"
}

# Check if AssetRipper is installed
assetripper_check_installed() {
    local assetripper_path=$(config_get assetripper.path)

    if [[ ! -x "$assetripper_path" ]]; then
        log_error "AssetRipper not found at: $assetripper_path"
        return $ERROR_DEPENDENCY
    fi

    log_debug "AssetRipper found at: $assetripper_path"
    return 0
}

# Check if AssetRipper server is running
_assetripper_check_server() {
    local base_url=$(_assetripper_get_url)
    curl -s -f "${base_url}/" > /dev/null 2>&1
}

# Start AssetRipper server
_assetripper_start_server() {
    local assetripper_path=$(config_get assetripper.path)
    local port=$(config_get assetripper.port)

    log_info "Starting AssetRipper server on port ${port}..."

    # Create log file
    ASSETRIPPER_LOG=$(config_get paths.logs)"/assetripper_$(date +%Y%m%d_%H%M%S).log"
    mkdir -p "$(dirname "$ASSETRIPPER_LOG")"

    # Start server in background
    "${assetripper_path}" --port "${port}" --launch-browser=false > "$ASSETRIPPER_LOG" 2>&1 &
    ASSETRIPPER_PID=$!

    # Wait for server to start
    local wait_time=0
    while ! _assetripper_check_server; do
        if [ $wait_time -ge 30 ]; then
            log_error "Server failed to start within 30 seconds"
            log_error "Check log: $ASSETRIPPER_LOG"
            return $ERROR_PROCESS
        fi
        sleep 1
        wait_time=$((wait_time + 1))
    done

    log_info "Server started successfully (PID: ${ASSETRIPPER_PID})"
    return 0
}

# Stop AssetRipper server
_assetripper_stop_server() {
    log_info "Stopping AssetRipper server..."

    if [ -n "${ASSETRIPPER_PID}" ]; then
        kill "${ASSETRIPPER_PID}" 2>/dev/null || true
        wait "${ASSETRIPPER_PID}" 2>/dev/null || true
    else
        # Try to kill by process name
        pkill -f "AssetRipper.GUI.Free" || true
    fi

    ASSETRIPPER_PID=""
}

# URL encode a path
_assetripper_urlencode() {
    local string="$1"
    printf %s "$string" | jq -sRr @uri
}

# Check if a path exists via API
_assetripper_check_path() {
    local path="$1"
    local base_url=$(_assetripper_get_url)
    local result

    # Try directory first
    result=$(curl -s "${base_url}/IO/Directory/Exists?Path=$(_assetripper_urlencode "$path")")
    if [ "$result" = "true" ]; then
        echo "true"
        return 0
    fi

    # Try file
    result=$(curl -s "${base_url}/IO/File/Exists?Path=$(_assetripper_urlencode "$path")")
    echo "$result"
}

# Load files into AssetRipper
_assetripper_load_files() {
    local input_path="$1"
    local base_url=$(_assetripper_get_url)

    log_info "Checking if input path exists: ${input_path}"
    local exists=$(_assetripper_check_path "$input_path")

    if [ "$exists" != "true" ]; then
        log_error "Input path does not exist: ${input_path}"
        return $ERROR_NOT_FOUND
    fi

    log_info "Loading files from: ${input_path}"

    # POST to LoadFolder endpoint
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "${base_url}/LoadFolder" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "path=${input_path}")

    local http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" != "302" ]; then
        log_error "Failed to load files. HTTP code: ${http_code}"
        return $ERROR_PROCESS
    fi

    log_info "Files loaded successfully. Waiting for processing..."

    # Wait for initial processing
    sleep 5
    return 0
}

# Export files to Unity project
_assetripper_export_files() {
    local output_path="$1"
    local base_url=$(_assetripper_get_url)

    log_info "Starting export to: ${output_path}"

    # Check if output directory is not empty
    if _assetripper_check_path "$output_path" | grep -q "true"; then
        local is_empty=$(curl -s "${base_url}/IO/Directory/Empty?Path=$(_assetripper_urlencode "$output_path")")
        if [ "$is_empty" = "false" ]; then
            log_warn "Output directory is not empty: ${output_path}"
            log_warn "Existing files may be overwritten"
        fi
    fi

    # POST to Export/UnityProject endpoint
    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "${base_url}/Export/UnityProject" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        --data-urlencode "path=${output_path}")

    local http_code=$(echo "$response" | tail -n1)

    if [ "$http_code" != "302" ]; then
        log_error "Failed to start export. HTTP code: ${http_code}"
        return $ERROR_PROCESS
    fi

    log_info "Export started successfully"
    return 0
}

# Monitor export progress
_assetripper_monitor_export() {
    local max_wait=$(config_get assetripper.timeout)
    local poll_interval=5
    local wait_time=0

    log_info "Monitoring export progress (timeout: ${max_wait}s)..."

    while [ $wait_time -lt $max_wait ]; do
        # Check log file for completion indicators
        # AssetRipper outputs: "Export : Finished post-export" when done
        if grep -q "Finished post-export\|Finished exporting assets" "$ASSETRIPPER_LOG" 2>/dev/null; then
            log_info "Export completed successfully!"
            return 0
        fi

        # Check for errors (but be careful with false positives)
        if tail -20 "$ASSETRIPPER_LOG" 2>/dev/null | grep -qi "error\|exception\|failed"; then
            # Only warn, don't fail (AssetRipper logs many non-critical warnings)
            if [ $((wait_time % 60)) -eq 0 ]; then
                log_debug "Note: Some warnings detected in log (may be non-critical)"
            fi
        fi

        sleep $poll_interval
        wait_time=$((wait_time + poll_interval))

        # Show progress every 30 seconds
        if [ $((wait_time % 30)) -eq 0 ]; then
            log_info "Still exporting... (${wait_time}s elapsed)"
        fi
    done

    log_warn "Export monitoring timed out after ${max_wait} seconds"
    log_warn "Export may still be running. Check the output directory and logs."
    return $ERROR_TIMEOUT
}

# Reset AssetRipper state
_assetripper_reset() {
    local base_url=$(_assetripper_get_url)

    log_debug "Resetting AssetRipper state..."
    curl -s -X POST "${base_url}/Reset" > /dev/null
    sleep 2
}

# Extract game assets (main function)
# Usage: assetripper_extract [game_dir] [unity_project]
assetripper_extract() {
    local game_dir="${1:-$(config_get paths.game_files)}"
    local unity_project="${2:-$(config_get paths.unity_project)}"

    log_info "Starting asset extraction..."
    log_debug "Game directory: $game_dir"
    log_debug "Unity project: $unity_project"

    # Check if AssetRipper is installed
    if ! assetripper_check_installed; then
        return $ERROR_DEPENDENCY
    fi

    # Check if jq is available (needed for URL encoding)
    if ! command -v jq &> /dev/null; then
        log_error "jq command not found. Install with: brew install jq"
        return $ERROR_DEPENDENCY
    fi

    # Find game data directory
    local game_data_dir
    if [[ -d "$game_dir/Erenshor_Data" ]]; then
        game_data_dir="$game_dir/Erenshor_Data"
    elif [[ -d "$game_dir" ]]; then
        game_data_dir="$game_dir"
    else
        log_error "Game data directory not found"
        return $ERROR_NOT_FOUND
    fi

    # AssetRipper extracts to a subdirectory structure
    # We extract to unity_project root, which creates:
    #   unity_project/ExportedProject/Assets/
    #   unity_project/ExportedProject/ProjectSettings/
    #   unity_project/AuxiliaryFiles/
    # We'll then move the contents up to the unity_project level
    local extract_dir="$unity_project"

    # Setup cleanup trap
    trap '_assetripper_stop_server' EXIT INT TERM

    # Step 1: Start server
    if ! _assetripper_start_server; then
        return $ERROR_PROCESS
    fi

    # Step 2: Load files
    if ! _assetripper_load_files "$game_data_dir"; then
        _assetripper_stop_server
        return $ERROR_PROCESS
    fi

    # Step 3: Export files
    if ! _assetripper_export_files "$extract_dir"; then
        _assetripper_stop_server
        return $ERROR_PROCESS
    fi

    # Step 4: Monitor progress
    if ! _assetripper_monitor_export; then
        log_warn "Export may not have completed successfully"
        _assetripper_stop_server
        return $ERROR_TIMEOUT
    fi

    # Step 5: Move extracted assets to final location
    log_info "Organizing extracted assets..."

    # AssetRipper creates:
    #   unity_project/ExportedProject/Assets/
    #   unity_project/ExportedProject/ProjectSettings/
    #   unity_project/AuxiliaryFiles/
    if [[ -d "$unity_project/ExportedProject" ]]; then
        # Move Assets (preserving existing Editor symlink)
        if [[ -d "$unity_project/ExportedProject/Assets" ]]; then
            log_info "Moving extracted Assets..."
            # Use rsync to merge, excluding Editor folder
            rsync -av --exclude='Editor' --exclude='Editor/' \
                "$unity_project/ExportedProject/Assets/" \
                "$unity_project/Assets/" || log_warn "Some files failed to copy"
        fi

        # Move ProjectSettings if needed
        if [[ -d "$unity_project/ExportedProject/ProjectSettings" && ! -d "$unity_project/ProjectSettings" ]]; then
            log_info "Moving ProjectSettings..."
            mv "$unity_project/ExportedProject/ProjectSettings" "$unity_project/" || true
        fi

        # Move Packages if needed
        if [[ -d "$unity_project/ExportedProject/Packages" && ! -d "$unity_project/Packages" ]]; then
            log_info "Moving Packages..."
            mv "$unity_project/ExportedProject/Packages" "$unity_project/" || true
        fi

        # Clean up temporary directories
        log_info "Cleaning up temporary files..."
        rm -rf "$unity_project/ExportedProject"
        rm -rf "$unity_project/AuxiliaryFiles"
    else
        log_error "Expected ExportedProject directory not found at: $unity_project/ExportedProject"
        log_error "AssetRipper may have failed or extracted to a different location"
        _assetripper_stop_server
        return $ERROR_PROCESS
    fi

    # Step 6: Copy NuGet packages and config files from source
    # These are not extracted by AssetRipper but are required for Unity compilation
    local repo_root="$(cd "$unity_project/../.." && pwd)"
    local src_assets="$repo_root/src/Assets"

    if [[ -d "$src_assets/Packages" ]]; then
        log_info "Copying NuGet packages from source..."
        mkdir -p "$unity_project/Assets/Packages"
        rsync -av "$src_assets/Packages/" "$unity_project/Assets/Packages/" || log_warn "Failed to copy some packages"
    else
        log_warn "Source Packages directory not found at: $src_assets/Packages"
    fi

    if [[ -f "$src_assets/NuGet.config" ]]; then
        log_info "Copying NuGet.config..."
        cp "$src_assets/NuGet.config" "$unity_project/Assets/" || log_warn "Failed to copy NuGet.config"
    fi

    if [[ -f "$src_assets/packages.config" ]]; then
        log_info "Copying packages.config..."
        cp "$src_assets/packages.config" "$unity_project/Assets/" || log_warn "Failed to copy packages.config"
    fi

    # Create Editor symlink (source code)
    if [[ -d "$src_assets/Editor" ]]; then
        log_info "Creating Editor symlink..."
        mkdir -p "$unity_project/Assets"
        ln -sf "../../../../src/Assets/Editor" "$unity_project/Assets/Editor"
    else
        log_warn "Source Editor directory not found at: $src_assets/Editor"
    fi

    # Step 7: Cleanup
    _assetripper_stop_server
    trap - EXIT INT TERM

    log_info "Asset extraction complete"
    log_info "Unity project ready at: $unity_project"
    log_info "Log file: $ASSETRIPPER_LOG"

    return 0
}

# Sync NuGet packages from source to Unity project
# Usage: assetripper_sync_packages [unity_project]
assetripper_sync_packages() {
    local unity_project="${1:-$(config_get paths.unity_project)}"
    local repo_root="$(cd "$(dirname "$unity_project")" && cd .. && pwd)"
    local src_assets="$repo_root/src/Assets"

    log_info "Syncing NuGet packages to Unity project..."
    log_debug "Source: $src_assets"
    log_debug "Target: $unity_project"

    # Check if source exists
    if [[ ! -d "$src_assets" ]]; then
        log_error "Source Assets directory not found: $src_assets"
        return $ERROR_NOT_FOUND
    fi

    # Copy NuGet packages
    if [[ -d "$src_assets/Packages" ]]; then
        log_info "Copying NuGet packages..."
        mkdir -p "$unity_project/Assets/Packages"
        rsync -av "$src_assets/Packages/" "$unity_project/Assets/Packages/" || {
            log_error "Failed to copy packages"
            return $ERROR_PROCESS
        }
        log_info "Packages copied successfully"
    else
        log_warn "Source Packages directory not found"
    fi

    # Copy NuGet config files
    local config_files=("NuGet.config" "packages.config")
    for file in "${config_files[@]}"; do
        if [[ -f "$src_assets/$file" ]]; then
            log_info "Copying $file..."
            cp "$src_assets/$file" "$unity_project/Assets/" || {
                log_warn "Failed to copy $file"
            }
        fi
    done

    log_info "Package sync complete"
    return 0
}

# Validate extraction
assetripper_validate() {
    local unity_project="${1:-$(config_get paths.unity_project)}"
    local required_dirs=("Assets/Scripts" "Assets/Resources" "Assets/Packages")
    local required_files=("Assets/NuGet.config" "Assets/packages.config")
    local errors=0

    log_info "Validating extracted assets..."

    # Check directories
    for dir in "${required_dirs[@]}"; do
        local full_path="$unity_project/$dir"
        if [[ ! -d "$full_path" ]]; then
            log_error "Required directory not found: $dir"
            ((errors++))
        else
            log_debug "Found: $dir"
        fi
    done

    # Check files
    for file in "${required_files[@]}"; do
        local full_path="$unity_project/$file"
        if [[ ! -f "$full_path" ]]; then
            log_warn "Required file not found: $file"
            # Don't count as error, just warn
        else
            log_debug "Found: $file"
        fi
    done

    if [[ $errors -eq 0 ]]; then
        log_info "Validation passed"
        return 0
    else
        log_error "Validation failed with $errors errors"
        return $ERROR_VALIDATION
    fi
}

# Clean extraction artifacts
assetripper_clean() {
    local unity_project="${1:-$(config_get paths.unity_project)}"
    local extract_dir="$unity_project/ExtractedAssets"

    if [[ -d "$extract_dir" ]]; then
        log_info "Cleaning extraction artifacts..."
        rm -rf "$extract_dir"
    fi
}

# Install AssetRipper
assetripper_install() {
    local install_dir="$HOME/Tools/AssetRipper"
    local version="1.3.4"

    log_info "Installing AssetRipper $version..."

    # Detect architecture
    local arch=$(uname -m)
    local download_file

    if [[ "$arch" == "arm64" ]]; then
        download_file="AssetRipper_mac_arm64.zip"
    else
        download_file="AssetRipper_mac_x64.zip"
    fi

    local download_url="https://github.com/AssetRipper/AssetRipper/releases/download/$version/$download_file"

    # Create temp directory
    local temp_dir=$(mktemp -d)
    cd "$temp_dir" || return $ERROR_GENERAL

    # Download
    log_info "Downloading from GitHub..."
    if ! curl -L "$download_url" -o "$download_file"; then
        log_error "Download failed"
        rm -rf "$temp_dir"
        return $ERROR_NETWORK
    fi

    # Extract
    log_info "Extracting..."
    if ! unzip -q "$download_file"; then
        log_error "Extraction failed"
        rm -rf "$temp_dir"
        return $ERROR_GENERAL
    fi

    # Install
    mkdir -p "$install_dir"
    cp -r ./* "$install_dir/"

    # Make executable
    chmod +x "$install_dir"/AssetRipper* 2>/dev/null || true

    # Cleanup
    rm -rf "$temp_dir"

    # Remove macOS quarantine attribute
    xattr -dr com.apple.quarantine "$install_dir" 2>/dev/null || true

    log_info "AssetRipper installed to: $install_dir"

    # Update config
    config_set "assetripper.path" "$install_dir/AssetRipper.GUI.Free"

    return 0
}
