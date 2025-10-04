#!/bin/bash

# Unity Batch Mode Export Wrapper
# Provides a user-friendly interface to the Unity batch mode export system

set -euo pipefail

# ============================================================================
# Constants
# ============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_VERSION_FILE="$PROJECT_DIR/ProjectSettings/ProjectVersion.txt"

# Available entity types (from ExportBatch.cs)
AVAILABLE_ENTITIES=(
    achievementtriggers ascensions books characters classes doors forges
    itembags items loottables miningnodes quests secretpassages
    skills spells spawnpoints teleportlocs treasurehunting treasurelocs
    waters wishingwells worldfactions zoneannounces zoneatlasentries zonelines
)

# ============================================================================
# Helper Functions
# ============================================================================

show_help() {
    cat << 'EOF'
Unity Batch Mode Export Wrapper

USAGE:
    export.sh [OPTIONS]

OPTIONS:
    -o, --output PATH       Output database path (required)
    -e, --entities LIST     Comma-separated entity types to export (optional, default: all)
    -l, --log-level LEVEL   Logging verbosity: quiet, normal, verbose (optional, default: normal)
    -h, --help              Show this help message

AVAILABLE ENTITY TYPES:
    achievementtriggers, ascensions, books, characters, classes, doors, forges,
    itembags, items, loottables, miningnodes, quests, secretpassages, skills,
    spells, spawnpoints, teleportlocs, treasurehunting, treasurelocs, waters,
    wishingwells, worldfactions, zoneannounces, zoneatlasentries, zonelines

ENTITY DEPENDENCIES:
    - items requires spells (for proc data)
    - characters requires spawnpoints (for IsUnique calculation)

EXAMPLES:
    # Export all entities
    ./export.sh -o erenshor.sqlite

    # Export specific entities
    ./export.sh -o game.sqlite -e items,spells,characters

    # Export with verbose logging
    ./export.sh -o output.sqlite -e items -l verbose

    # Export with quiet logging (errors only)
    ./export.sh -o minimal.sqlite -e spells -l quiet

EOF
}

error() {
    echo "ERROR: $1" >&2
    exit 1
}

warn() {
    echo "WARNING: $1" >&2
}

info() {
    echo "INFO: $1" >&2
}

# ============================================================================
# Unity Detection
# ============================================================================

detect_unity_version() {
    if [[ ! -f "$PROJECT_VERSION_FILE" ]]; then
        error "Cannot find ProjectVersion.txt at: $PROJECT_VERSION_FILE"
    fi

    # Extract version from m_EditorVersion line
    local version=$(grep '^m_EditorVersion:' "$PROJECT_VERSION_FILE" | sed 's/m_EditorVersion: //' | tr -d '\r\n')

    if [[ -z "$version" ]]; then
        error "Cannot parse Unity version from ProjectVersion.txt"
    fi

    echo "$version"
}

find_unity_installation() {
    local version=$1

    # Common macOS Unity installation paths
    local unity_paths=(
        "/Applications/Unity/Hub/Editor/$version/Unity.app/Contents/MacOS/Unity"
        "/Applications/Unity/Unity.app/Contents/MacOS/Unity"
        "$HOME/Applications/Unity/Hub/Editor/$version/Unity.app/Contents/MacOS/Unity"
    )

    # Try each path
    for path in "${unity_paths[@]}"; do
        if [[ -x "$path" ]]; then
            echo "$path"
            return 0
        fi
    done

    # Not found
    error "Cannot find Unity $version installation. Searched:
  ${unity_paths[*]}"
}

# ============================================================================
# Entity Validation
# ============================================================================

validate_entity() {
    local entity=$1
    local entity_lower=$(echo "$entity" | tr '[:upper:]' '[:lower:]')

    for valid in "${AVAILABLE_ENTITIES[@]}"; do
        if [[ "$entity_lower" == "$valid" ]]; then
            return 0
        fi
    done

    return 1
}

get_entity_dependency() {
    local entity=$1
    case "$entity" in
        items)
            echo "spells"
            ;;
        characters)
            echo "spawnpoints"
            ;;
        *)
            echo ""
            ;;
    esac
}

resolve_dependencies() {
    # Read entities from global ENTITY_ARRAY
    # Append dependencies to global ENTITY_ARRAY
    
    local i=0
    local original_count=${#ENTITY_ARRAY[@]}
    
    while [[ $i -lt ${#ENTITY_ARRAY[@]} ]]; do
        local entity="${ENTITY_ARRAY[$i]}"
        local entity_lower=$(echo "$entity" | tr '[:upper:]' '[:lower:]')
        local dep=$(get_entity_dependency "$entity_lower")

        if [[ -n "$dep" ]]; then
            # Check if dependency is already in the list
            local found=0
            for e in "${ENTITY_ARRAY[@]}"; do
                if [[ "$(echo "$e" | tr '[:upper:]' '[:lower:]')" == "$dep" ]]; then
                    found=1
                    break
                fi
            done

            # Add dependency if not present
            if [[ $found -eq 0 ]]; then
                ENTITY_ARRAY+=("$dep")
                info "Auto-added dependency: $dep (required by $entity_lower)"
            fi
        fi

        i=$((i + 1))
    done
}

# ============================================================================
# Argument Parsing
# ============================================================================

OUTPUT_PATH=""
ENTITIES=""
LOG_LEVEL="normal"

while [[ $# -gt 0 ]]; do
    case $1 in
        -o|--output)
            OUTPUT_PATH="$2"
            shift 2
            ;;
        -e|--entities)
            ENTITIES="$2"
            shift 2
            ;;
        -l|--log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            error "Unknown option: $1

Use --help for usage information."
            ;;
    esac
done

# Validate required arguments
if [[ -z "$OUTPUT_PATH" ]]; then
    error "Missing required argument: -o/--output

Use --help for usage information."
fi

# Convert relative path to absolute path (Unity requires absolute paths)
if [[ ! "$OUTPUT_PATH" = /* ]]; then
    OUTPUT_PATH="$(cd "$(dirname "$OUTPUT_PATH")" 2>/dev/null && pwd)/$(basename "$OUTPUT_PATH")" || OUTPUT_PATH="$PWD/$OUTPUT_PATH"
fi

# Validate log level
case "$LOG_LEVEL" in
    quiet|normal|verbose)
        ;;
    *)
        error "Invalid log level: $LOG_LEVEL. Valid options: quiet, normal, verbose"
        ;;
esac

# Validate and resolve entity list
if [[ -n "$ENTITIES" ]]; then
    # Split comma-separated list into array
    IFS=',' read -ra ENTITY_ARRAY <<< "$ENTITIES"

    # Validate each entity
    for entity in "${ENTITY_ARRAY[@]}"; do
        entity=$(echo "$entity" | xargs) # trim whitespace
        if ! validate_entity "$entity"; then
            error "Unknown entity type: $entity

Available types: ${AVAILABLE_ENTITIES[*]}"
        fi
    done

    # Resolve dependencies
    resolve_dependencies

    # Rebuild comma-separated list
    ENTITIES=$(IFS=,; echo "${ENTITY_ARRAY[*]}")
fi

# ============================================================================
# Unity Execution
# ============================================================================

# Detect Unity version and installation
UNITY_VERSION=$(detect_unity_version)
info "Detected Unity version: $UNITY_VERSION"

UNITY_PATH=$(find_unity_installation "$UNITY_VERSION")
info "Found Unity at: $UNITY_PATH"

# Build Unity command
UNITY_CMD=(
    "$UNITY_PATH"
    -batchmode
    -quit
    -projectPath "$PROJECT_DIR"
    -executeMethod ExportBatch.Run
    -dbPath "$OUTPUT_PATH"
    -logLevel "$LOG_LEVEL"
    -logFile -
)

# Add entities if specified
if [[ -n "$ENTITIES" ]]; then
    UNITY_CMD+=(-entities "$ENTITIES")
fi

# Execute Unity
info "Starting export..."
info "Command: ${UNITY_CMD[*]}"
echo ""

# Run Unity and capture exit code
set +e
"${UNITY_CMD[@]}"
EXIT_CODE=$?
set -e

echo ""

# Parse output for success/failure
if [[ $EXIT_CODE -eq 0 ]]; then
    info "Export completed successfully"
    info "Database written to: $OUTPUT_PATH"
    exit 0
else
    error "Export failed with exit code $EXIT_CODE"
fi
