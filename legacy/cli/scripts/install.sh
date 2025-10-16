#!/usr/bin/env bash
# scripts/install.sh - Install Erenshor automation pipeline

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}ℹ${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warning() { echo -e "${YELLOW}⚠${NC} $*"; }
error() { echo -e "${RED}✗${NC} $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTOMATION_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo ""
echo "======================================"
echo "  Erenshor Pipeline Installer"
echo "======================================"
echo ""

# Check prerequisites
info "Checking prerequisites..."

if [[ "$(uname)" != "Darwin" ]]; then
    error "This installer is for macOS only"
    exit 1
fi
success "Running on macOS"

if [[ "${BASH_VERSINFO[0]}" -lt 4 ]]; then
    warning "Bash version ${BASH_VERSION} detected (recommend 5+)"
    warning "Install with: brew install bash"
else
    success "Bash ${BASH_VERSION}"
fi

echo ""

# Install method
info "Choose installation method:"
echo ""
echo "  1) Add to PATH (recommended)"
echo "  2) Create symlink in /usr/local/bin"
echo "  3) Skip (manual setup)"
echo ""
read -p "Select [1-3]: " choice

case "$choice" in
    1)
        # Add to PATH
        SHELL_RC=""
        if [[ -f "$HOME/.zshrc" ]]; then
            SHELL_RC="$HOME/.zshrc"
        elif [[ -f "$HOME/.bashrc" ]]; then
            SHELL_RC="$HOME/.bashrc"
        elif [[ -f "$HOME/.bash_profile" ]]; then
            SHELL_RC="$HOME/.bash_profile"
        fi

        if [[ -n "$SHELL_RC" ]]; then
            PATH_LINE="export PATH=\"$AUTOMATION_ROOT/bin:\$PATH\""

            if grep -q "$PATH_LINE" "$SHELL_RC"; then
                warning "Already in PATH"
            else
                echo "" >> "$SHELL_RC"
                echo "# Erenshor automation pipeline" >> "$SHELL_RC"
                echo "$PATH_LINE" >> "$SHELL_RC"
                success "Added to PATH in $SHELL_RC"
                info "Restart your shell or run: source $SHELL_RC"
            fi
        else
            warning "Could not detect shell config file"
            echo "Add this to your shell profile:"
            echo "  export PATH=\"$AUTOMATION_ROOT/bin:\$PATH\""
        fi
        ;;
    2)
        # Create symlink
        if [[ -L "/usr/local/bin/erenshor" ]]; then
            warning "Symlink already exists"
        else
            sudo ln -s "$AUTOMATION_ROOT/bin/erenshor" /usr/local/bin/erenshor
            success "Created symlink in /usr/local/bin"
        fi
        ;;
    3)
        info "Skipping installation"
        echo "Run manually with: $AUTOMATION_ROOT/bin/erenshor"
        ;;
    *)
        error "Invalid choice"
        exit 1
        ;;
esac

echo ""

# Create config directory
info "Setting up configuration..."
mkdir -p "$HOME/.erenshor"/{logs,backups,output,game}
success "Created ~/.erenshor directories"

# Create default config if not exists
if [[ ! -f "$HOME/.erenshor/config.toml" ]]; then
    "$AUTOMATION_ROOT/bin/erenshor" config create 2>/dev/null || true
    success "Created default configuration"
else
    warning "Configuration already exists"
fi

echo ""

# Check dependencies
info "Checking dependencies..."

check_dep() {
    local name="$1"
    local cmd="$2"
    local install_hint="$3"

    if command -v "$cmd" &>/dev/null; then
        success "$name installed"
        return 0
    else
        error "$name not found"
        if [[ -n "$install_hint" ]]; then
            echo "  Install with: $install_hint"
        fi
        return 1
    fi
}

DEPS_OK=true
check_dep "SteamCMD" "steamcmd" "brew install steamcmd" || DEPS_OK=false
check_dep "SQLite" "sqlite3" "" || DEPS_OK=false
check_dep "jq (optional)" "jq" "brew install jq" || true

echo ""

# Offer to download AssetRipper
if [[ ! -f "$HOME/Tools/AssetRipper/AssetRipperConsole" ]]; then
    warning "AssetRipper not found"
    read -p "Download and install AssetRipper? [Y/n]: " install_ar

    if [[ -z "$install_ar" || "$install_ar" =~ ^[Yy] ]]; then
        info "Installing AssetRipper..."

        # Detect architecture
        ARCH=$(uname -m)
        if [[ "$ARCH" == "arm64" ]]; then
            DOWNLOAD_FILE="AssetRipper_mac_arm64.zip"
        else
            DOWNLOAD_FILE="AssetRipper_mac_x64.zip"
        fi

        DOWNLOAD_URL="https://github.com/AssetRipper/AssetRipper/releases/download/1.3.4/$DOWNLOAD_FILE"
        TEMP_DIR=$(mktemp -d)

        cd "$TEMP_DIR"
        curl -L "$DOWNLOAD_URL" -o "$DOWNLOAD_FILE"
        unzip -q "$DOWNLOAD_FILE"

        mkdir -p "$HOME/Tools/AssetRipper"
        cp -r ./* "$HOME/Tools/AssetRipper/"
        chmod +x "$HOME/Tools/AssetRipper"/AssetRipper* 2>/dev/null || true
        xattr -dr com.apple.quarantine "$HOME/Tools/AssetRipper" 2>/dev/null || true

        rm -rf "$TEMP_DIR"

        success "AssetRipper installed to ~/Tools/AssetRipper"
    fi
fi

echo ""

# Summary
echo "======================================"
echo "  Installation Complete!"
echo "======================================"
echo ""

if [[ "$DEPS_OK" == false ]]; then
    warning "Some dependencies are missing. Install them before running."
    echo ""
fi

echo "Next steps:"
echo ""
echo "  1. Verify installation:"
echo "     erenshor doctor"
echo ""
echo "  2. Edit configuration:"
echo "     erenshor config edit"
echo ""
echo "  3. Run first update:"
echo "     erenshor update"
echo ""
echo "Documentation: $AUTOMATION_ROOT/README.md"
echo ""
