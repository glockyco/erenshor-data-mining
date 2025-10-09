#!/usr/bin/env bash
# lib/core/state.sh - State management

# Guard against multiple sourcing
[[ -n "${STATE_LOADED:-}" ]] && return 0
readonly STATE_LOADED=1

# State file location - now in project directory
REPO_ROOT="${REPO_ROOT:-$(get_repo_root)}"
ERENSHOR_STATE="${ERENSHOR_STATE:-$REPO_ROOT/.erenshor/state.json}"

# Initialize state file with v2.0 structure
# Only creates file if it doesn't exist - no migration from older versions
state_init() {
    local state_file="${1:-$ERENSHOR_STATE}"
    local state_dir=$(dirname "$state_file")

    mkdir -p "$state_dir"

    # Create v2.0 state file if doesn't exist
    if [[ ! -f "$state_file" ]]; then
        cat > "$state_file" << 'EOF'
{
  "version": "2.0",
  "last_update": null,
  "current_operation": "idle",
  "variants": {
    "main": {
      "game": {
        "build_id": null,
        "last_checked": null,
        "last_downloaded": null,
        "files_path": null,
        "size_bytes": 0
      },
      "database": {
        "path": null,
        "last_export": null,
        "size_bytes": 0,
        "entity_counts": {}
      },
      "unity": {
        "last_extraction": null,
        "project_path": null
      }
    },
    "playtest": {
      "game": {
        "build_id": null,
        "last_checked": null,
        "last_downloaded": null,
        "files_path": null,
        "size_bytes": 0
      },
      "database": {
        "path": null,
        "last_export": null,
        "size_bytes": 0,
        "entity_counts": {}
      },
      "unity": {
        "last_extraction": null,
        "project_path": null
      }
    },
    "demo": {
      "game": {
        "build_id": null,
        "last_checked": null,
        "last_downloaded": null,
        "files_path": null,
        "size_bytes": 0
      },
      "database": {
        "path": null,
        "last_export": null,
        "size_bytes": 0,
        "entity_counts": {}
      },
      "unity": {
        "last_extraction": null,
        "project_path": null
      }
    }
  },
  "pipeline": {
    "last_run": null,
    "duration_seconds": 0,
    "status": "idle",
    "stages": {}
  }
}
EOF
    fi
}

# Read state value using jq
state_get() {
    local key="$1"
    local default="${2:-null}"
    local state_file="${ERENSHOR_STATE}"

    if [[ ! -f "$state_file" ]]; then
        echo "$default"
        return
    fi

    if command_exists jq; then
        jq -r ".${key} // \"$default\"" "$state_file" 2>/dev/null || echo "$default"
    else
        # Fallback without jq (limited functionality)
        echo "$default"
    fi
}

# Set state value using jq
state_set() {
    local key="$1"
    local value="$2"
    local state_file="${ERENSHOR_STATE}"

    if [[ ! -f "$state_file" ]]; then
        state_init
    fi

    if command_exists jq; then
        local temp_file="${state_file}.tmp"
        # Handle null values
        if [[ "$value" == "null" ]]; then
            jq ".${key} = null" "$state_file" > "$temp_file"
        else
            jq ".${key} = \"$value\"" "$state_file" > "$temp_file"
        fi
        mv "$temp_file" "$state_file"
    fi
}

# Set state value (numeric)
state_set_number() {
    local key="$1"
    local value="$2"
    local state_file="${ERENSHOR_STATE}"

    if [[ ! -f "$state_file" ]]; then
        state_init
    fi

    if command_exists jq; then
        local temp_file="${state_file}.tmp"
        jq ".${key} = $value" "$state_file" > "$temp_file"
        mv "$temp_file" "$state_file"
    fi
}

# Set state object
state_set_object() {
    local key="$1"
    local json="$2"
    local state_file="${ERENSHOR_STATE}"

    if [[ ! -f "$state_file" ]]; then
        state_init
    fi

    if command_exists jq; then
        local temp_file="${state_file}.tmp"
        # Validate JSON first, use empty object if invalid
        if ! echo "$json" | jq empty 2>/dev/null; then
            json="{}"
        fi
        # Use --argjson to safely pass JSON object
        jq --argjson obj "$json" ".${key} = \$obj" "$state_file" > "$temp_file" 2>/dev/null
        if [[ $? -eq 0 ]]; then
            mv "$temp_file" "$state_file"
        else
            rm -f "$temp_file"
        fi
    fi
}

# Update last update timestamp
state_update_timestamp() {
    state_set "last_update" "$(timestamp_iso)"
}

# Set current operation
state_set_operation() {
    local operation="$1"
    state_set "current_operation" "$operation"
    state_update_timestamp
}

# Record game update
state_record_game() {
    local build_id="$1"
    local files_path="$2"
    local size_bytes="${3:-0}"

    state_set "game.build_id" "$build_id"
    state_set "game.last_downloaded" "$(timestamp_iso)"
    state_set "game.files_path" "$files_path"
    state_set_number "game.size_bytes" "$size_bytes"
    state_update_timestamp
}

# Record database export
state_record_export() {
    local db_path="$1"
    local size_bytes="${2:-0}"
    local entity_counts="${3:-{}}"

    state_set "database.path" "$db_path"
    state_set "database.last_export" "$(timestamp_iso)"
    state_set_number "database.size_bytes" "$size_bytes"
    state_set_object "database.entity_counts" "$entity_counts"
    state_update_timestamp
}

# Record pipeline run
state_record_pipeline() {
    local status="$1"
    local duration="${2:-0}"
    local stages="${3:-{}}"

    state_set "pipeline.last_run" "$(timestamp_iso)"
    state_set "pipeline.status" "$status"
    state_set_number "pipeline.duration_seconds" "$duration"
    state_set_object "pipeline.stages" "$stages"
    state_update_timestamp
}

# Print state (for debugging)
state_print() {
    local state_file="${ERENSHOR_STATE}"

    if [[ ! -f "$state_file" ]]; then
        echo "No state file found"
        return
    fi

    if command_exists jq; then
        jq '.' "$state_file"
    else
        cat "$state_file"
    fi
}

# ============================================================================
# Variant-Specific State Functions
# ============================================================================

# Get variant-specific state value
state_get_variant() {
    local variant="$1"
    local key="$2"
    local default="${3:-null}"

    state_get "variants.$variant.$key" "$default"
}

# Set variant-specific state value
state_set_variant() {
    local variant="$1"
    local key="$2"
    local value="$3"

    state_set "variants.$variant.$key" "$value"
}

# Set variant-specific state number
state_set_variant_number() {
    local variant="$1"
    local key="$2"
    local value="$3"

    state_set_number "variants.$variant.$key" "$value"
}

# Set variant-specific state object
state_set_variant_object() {
    local variant="$1"
    local key="$2"
    local json="$3"

    state_set_object "variants.$variant.$key" "$json"
}

# Record variant game download
state_record_variant_game() {
    local variant="$1"
    local build_id="$2"
    local files_path="$3"
    local size_bytes="${4:-0}"

    state_set_variant "$variant" "game.build_id" "$build_id"
    state_set_variant "$variant" "game.last_downloaded" "$(timestamp_iso)"
    state_set_variant "$variant" "game.files_path" "$files_path"
    state_set_variant_number "$variant" "game.size_bytes" "$size_bytes"
    state_update_timestamp
}

# Record variant database export
state_record_variant_export() {
    local variant="$1"
    local db_path="$2"
    local size_bytes="${3:-0}"
    local entity_counts="${4:-{}}"

    state_set_variant "$variant" "database.path" "$db_path"
    state_set_variant "$variant" "database.last_export" "$(timestamp_iso)"
    state_set_variant_number "$variant" "database.size_bytes" "$size_bytes"
    state_set_variant_object "$variant" "database.entity_counts" "$entity_counts"
    state_update_timestamp
}

# Initialize variant state if needed
state_init_variant() {
    local variant="$1"
    local state_file="${ERENSHOR_STATE}"

    # Check if variant state exists
    if command_exists jq; then
        local has_variant=$(jq -r ".variants.$variant // \"null\"" "$state_file" 2>/dev/null)
        if [[ "$has_variant" == "null" ]]; then
            # Initialize variant state
            state_set_variant_object "$variant" "" "{
                \"game\": {
                    \"build_id\": null,
                    \"last_checked\": null,
                    \"last_downloaded\": null,
                    \"files_path\": null,
                    \"size_bytes\": 0
                },
                \"database\": {
                    \"path\": null,
                    \"last_export\": null,
                    \"size_bytes\": 0,
                    \"entity_counts\": {}
                },
                \"unity\": {
                    \"last_extraction\": null,
                    \"project_path\": null
                }
            }"
        fi
    fi
}
