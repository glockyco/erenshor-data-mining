#!/usr/bin/env python3
"""End-of-session teardown for the refreshing-game-data workflow.

Stops the maps dev server, kills the Erenshor Playtest game and its wine
satellites, quits Unity Hub if it was opened for licensing, and restores
the interactive map's DB symlink to the main variant.

Idempotent. Targets only macOS (the project's only supported workstation).

Why this exists as a script instead of a prose checklist:
- `pkill -f wineserver` does not kill the wine processes that hold BepInEx
  console windows open — those are `conhost.exe` and `UnityCrashHandler64.exe`
  processes that get reparented to launchd (PID 1) on game exit.
- macOS's bash `kill` builtin rejects multi-PID invocations
  (`kill -9 a b c` -> "too many jobs or processes specified") and the
  long-form signal name (`kill -KILL pid` -> "invalid signal name"), so the
  cleanup gets done wrong by hand every time.
- The map DB symlink shared between variants is the highest-impact piece of
  shared state and the easiest to forget to reset.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Match-by-substring patterns against `ps -axo command`.
# "Erenshor Playtest" matches both the game exe and its UnityCrashHandler64
# satellites whose cmdline contains the install path.
GAME_PATTERNS: list[tuple[str, str]] = [
    ("Erenshor Playtest", "playtest game/satellite"),
]

# conhost is killed only when at least one game/satellite was found,
# so that an unrelated CrossOver game's conhost is not collateral.
CONHOST_PATTERN = "conhost.exe"

# Map-dev port and the BepInEx mod ports that should be free after teardown.
SESSION_PORTS = (5173, 18585, 18586, 18590, 38729)


def kill(pid: int, label: str) -> bool:
    """Send SIGKILL. Returns True if the kill landed, False if process was already gone."""
    try:
        os.kill(pid, signal.SIGKILL)
        print(f"  killed {label} pid={pid}")
        return True
    except ProcessLookupError:
        return False


def kill_maps_dev() -> int:
    """Kill the Vite dev server holding port 5173. Returns count."""
    result = subprocess.run(
        ["lsof", "-ti", ":5173", "-P", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    count = 0
    for pid_str in result.stdout.strip().splitlines():
        if pid_str and kill(int(pid_str), "maps dev (port 5173)"):
            count += 1
    return count


def _is_recent(etime: str, hours: int = 12) -> bool:
    """Parse `ps -axo etime` and return True if the process started <hours hours ago.

    Format: `[[DD-]HH:]MM:SS`. Absence of `-` means same day; absence of leading
    `HH:` means <1 hour.
    """
    if "-" in etime:
        return False
    if etime.count(":") < 2:
        return True
    return int(etime.split(":")[0]) < hours


def kill_game_and_satellites() -> int:
    """Kill all processes matching GAME_PATTERNS. Returns count killed."""
    ps = subprocess.run(
        ["ps", "-axo", "pid,command"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    count = 0
    for line in ps.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) != 2 or not parts[0].isdigit():
            continue
        pid, cmd = int(parts[0]), parts[1]
        for substr, label in GAME_PATTERNS:
            if substr in cmd and kill(pid, label):
                count += 1
                break
    return count


def kill_recent_conhost() -> int:
    """Kill recent conhost.exe processes (<12h old) — these hold BepInEx console windows."""
    ps = subprocess.run(
        ["ps", "-axo", "pid,etime,command"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    count = 0
    for line in ps.splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) != 3 or not parts[0].isdigit():
            continue
        pid, etime, cmd = int(parts[0]), parts[1], parts[2]
        if CONHOST_PATTERN in cmd and _is_recent(etime) and kill(pid, "conhost (BepInEx console window)"):
            count += 1
    return count


def quit_unity_hub() -> None:
    """Best-effort quit of Unity Hub. Silent if not running."""
    subprocess.run(
        ["osascript", "-e", 'quit app "Unity Hub"'],
        capture_output=True,
        text=True,
        check=False,
    )
    subprocess.run(
        ["pkill", "-9", "-f", "UnityLicensingClient"],
        capture_output=True,
        check=False,
    )


def restore_main_symlink(repo_root: Path) -> bool:
    """Atomically point the map DB symlink at main. Returns True on success."""
    link = repo_root / "src" / "maps" / "static" / "db" / "erenshor.sqlite"
    target = repo_root / "variants" / "main" / "erenshor-main.sqlite"
    if not target.exists():
        print(f"  WARNING: main DB not found at {target}; symlink not restored", file=sys.stderr)
        return False
    tmp = link.with_suffix(".tmp")
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    tmp.symlink_to(target)
    tmp.replace(link)
    print(f"  symlink -> {target}")
    return True


def check_ports_clear() -> list[str]:
    """Return list of `lsof` output lines for any session port still held."""
    args = ["lsof", "-P", "-sTCP:LISTEN"]
    for port in SESSION_PORTS:
        args.extend(["-i", f":{port}"])
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    out = result.stdout.strip()
    return out.splitlines() if out else []


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="repo root (default: cwd)",
    )
    parser.add_argument(
        "--no-symlink-restore",
        action="store_true",
        help="skip restoring the main map DB symlink",
    )
    parser.add_argument(
        "--no-unity-hub",
        action="store_true",
        help="leave Unity Hub running",
    )
    args = parser.parse_args()

    print("Stopping maps dev server...")
    kill_maps_dev()

    print("Stopping game and wine satellites...")
    killed_game = kill_game_and_satellites()
    if killed_game > 0:
        # Only sweep conhost if game was actually running — protects unrelated wine games.
        print("Stopping BepInEx console windows (conhost)...")
        kill_recent_conhost()
    else:
        print("  no game processes found; skipping conhost sweep")

    if not args.no_unity_hub:
        print("Quitting Unity Hub (best effort)...")
        quit_unity_hub()

    time.sleep(1)

    if not args.no_symlink_restore:
        print("Restoring main map symlink...")
        restore_main_symlink(args.repo_root)

    still_held = check_ports_clear()
    if still_held:
        print("\nWARNING: session ports still held:", file=sys.stderr)
        for line in still_held:
            print(f"  {line}", file=sys.stderr)
        return 1

    print("\nTeardown complete; all session ports clear.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
