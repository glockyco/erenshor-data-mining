#!/usr/bin/env bash
# Run a command with the project toolchain on PATH.
#
# Git hooks are not always invoked from a shell that entered the dev shell.
# GUI clients spawn git from the launchd session, whose PATH is /usr/bin:/bin
# and nothing else, so a hook calling `uv` there dies with exit 127 and the
# push fails for reasons unrelated to the change being pushed.
#
# The environment is entered here instead: directly when the toolchain is
# already present, through direnv when its cache is warm, and through the flake
# otherwise.
set -euo pipefail

if [ "$#" -eq 0 ]; then
    echo "usage: with-dev-env.sh <command> [args...]" >&2
    exit 64
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Nix installs into profiles that a GUI process never sources, so direnv and
# nix themselves have to be findable before they can provide anything else.
for candidate in \
    "/run/current-system/sw/bin" \
    "/etc/profiles/per-user/${USER:-$(id -un)}/bin" \
    "${HOME}/.nix-profile/bin" \
    "/nix/var/nix/profiles/default/bin"; do
    if [ -d "$candidate" ]; then
        case ":${PATH}:" in
        *":${candidate}:"*) ;;
        *) PATH="${PATH}:${candidate}" ;;
        esac
    fi
done
export PATH

# `uv` stands in for the whole shell: nothing provides it but the dev shell.
if command -v uv >/dev/null 2>&1; then
    exec "$@"
fi

# Probe before delegating: an unapproved .envrc makes direnv refuse, and that
# refusal must not be reported as the hook's own failure. Probing keeps a real
# failure of the wrapped command distinguishable from an unusable direnv.
if command -v direnv >/dev/null 2>&1 && [ -f "${repo_root}/.envrc" ] &&
    direnv exec "$repo_root" true >/dev/null 2>&1; then
    exec direnv exec "$repo_root" "$@"
fi

if command -v nix >/dev/null 2>&1; then
    exec nix develop "$repo_root" --command "$@"
fi

echo "with-dev-env.sh: no project toolchain and no way to enter the dev shell." >&2
echo "Install Nix and run 'direnv allow', or run the command inside 'nix develop'." >&2
exit 127
