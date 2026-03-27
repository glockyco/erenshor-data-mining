#!/usr/bin/env python3
"""Capture consistent NPC screenshots via HotRepl.

Positions the camera at a fixed distance in front of the NPC at marker
height, disabling the camera follow script for the duration.

Usage:
    uv run python scripts/capture-npc-screenshot.py "Alice Hewer"
    uv run python scripts/capture-npc-screenshot.py "Timothy Allorn" -d 5
    uv run python scripts/capture-npc-screenshot.py --pos 202,52.9,344.8 -o aragath.png
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
import time
from pathlib import Path

WINE_TEMP = Path.home() / (
    "Library/Application Support/CrossOver/Bottles/Steam/drive_c/"
    "users/crossover/AppData/Local/Temp/Burgee Media/Erenshor"
)
CAPTURE_FILENAME = "npc_capture.png"
WINE_CAPTURE_PATH = "C:/users/crossover/AppData/Local/Temp/Burgee Media/Erenshor/" + CAPTURE_FILENAME
MARKER_HEIGHT_OFFSET = 2.5

# C# snippets to hide/show SimPlayers during capture.
HIDE_SIMPLAYERS = (
    " foreach (var _sp in UnityEngine.Object.FindObjectsOfType<SimPlayer>()) _sp.gameObject.SetActive(false);"
)
SHOW_SIMPLAYERS = " foreach (var _sp in Resources.FindObjectsOfTypeAll<SimPlayer>()) _sp.gameObject.SetActive(true);"


async def eval_cs(code: str, *, timeout_ms: int = 10000) -> str:
    from erenshor.application.eval.client import EvalClient, EvalError

    client = EvalClient()
    try:
        await client.connect()
        resp = await client.eval(code, timeout_ms=timeout_ms)
    except EvalError as exc:
        return f"ERROR:{exc}"
    finally:
        await client.close()
    return str(resp.get("result", resp.get("value", "")))


def build_npc_capture_code(npc_name: str, distance: float) -> str:
    """Move player + camera in front of NPC and screenshot.

    Moves the player near the NPC (so markers/nameplates aren't distance-culled),
    then positions the camera at marker height along the NPC's forward vector.
    """
    return (
        f"var _npc = UnityEngine.Object.FindObjectsOfType<NPC>()"
        f'.FirstOrDefault(n => n.NPCName == "{npc_name}");'
        f' var _result = "ERROR:NPC not found in current scene";'
        f" if (_npc != null) {{"
        f"   var _p = _npc.transform.position;"
        f"   var _fwd = _npc.transform.forward;"
        f"   var _my = _p.y + {MARKER_HEIGHT_OFFSET}f;"
        f"   var _camPos = new UnityEngine.Vector3("
        f"     _p.x + _fwd.x * {distance}f, _my, _p.z + _fwd.z * {distance}f);"
        f"   var _player = GameData.PlayerControl;"
        f"   var _cc = _player.GetComponent<UnityEngine.CharacterController>();"
        f"   _cc.enabled = false;"
        f"   _player.transform.position = _camPos;"
        f'   var _cam = UnityEngine.GameObject.Find("FPVCam");'
        f"   _cam.GetComponent<FPVCam>().enabled = false;"
        f"   _cam.transform.position = _camPos;"
        f"   _cam.transform.LookAt(new UnityEngine.Vector3(_p.x, _my, _p.z));"
        + HIDE_SIMPLAYERS
        + f' UnityHelpers.Screenshot("{WINE_CAPTURE_PATH}");'
        f'   _result = "OK";'
        " }"
        " _result"
    )


def build_pos_capture_code(x: float, y: float, z: float, distance: float) -> str:
    """Move player + camera east of a static position and screenshot."""
    my = y + MARKER_HEIGHT_OFFSET
    return (
        f"var _player = GameData.PlayerControl;"
        f" var _cc = _player.GetComponent<UnityEngine.CharacterController>();"
        f" _cc.enabled = false;"
        f" _player.transform.position = new UnityEngine.Vector3({x + distance}f, {my}f, {z}f);"
        f' var _cam = UnityEngine.GameObject.Find("FPVCam");'
        f" _cam.GetComponent<FPVCam>().enabled = false;"
        f" _cam.transform.position = new UnityEngine.Vector3({x + distance}f, {my}f, {z}f);"
        f" _cam.transform.LookAt(new UnityEngine.Vector3({x}f, {my}f, {z}f));"
        + HIDE_SIMPLAYERS
        + f' UnityHelpers.Screenshot("{WINE_CAPTURE_PATH}");'
        ' "OK"'
    )


async def reset_repl() -> None:
    """Reset REPL state to avoid stale variable conflicts between captures."""
    from erenshor.application.eval.client import EvalClient

    client = EvalClient()
    try:
        await client.connect()
        await client.reset()
    finally:
        await client.close()


async def capture(code: str, label: str, output: Path) -> None:
    await reset_repl()

    src = WINE_TEMP / CAPTURE_FILENAME
    if src.exists():
        src.unlink()

    result = await eval_cs(code)

    if result.startswith("ERROR:"):
        print(f"  Error: {result[6:]}", file=sys.stderr)
        # Re-enable camera controller on failure
        await eval_cs(
            'var _cam = UnityEngine.GameObject.Find("FPVCam");'
            " _cam.GetComponent<FPVCam>().enabled = true;"
            " GameData.PlayerControl.GetComponent<UnityEngine.CharacterController>().enabled = true;"
            ' "OK"'
        )
        sys.exit(1)

    print(f"  Positioned camera for {label}")

    for _attempt in range(20):
        if src.exists():
            break
        time.sleep(0.2)
    else:
        print("  Error: screenshot not written after 4s", file=sys.stderr)
        await eval_cs(
            'var _cam = UnityEngine.GameObject.Find("FPVCam");'
            " _cam.GetComponent<FPVCam>().enabled = true;"
            " GameData.PlayerControl.GetComponent<UnityEngine.CharacterController>().enabled = true;"
            ' "OK"'
        )
        sys.exit(1)

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(output))
    print(f"  Saved to {output}")

    # Re-enable camera follow
    await eval_cs(
        'var _cam = UnityEngine.GameObject.Find("FPVCam");'
        " _cam.GetComponent<FPVCam>().enabled = true;"
        " GameData.PlayerControl.GetComponent<UnityEngine.CharacterController>().enabled = true;"
        + SHOW_SIMPLAYERS
        + ' "OK"'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture consistent NPC screenshots via HotRepl.")
    parser.add_argument("npc_name", nargs="?", default=None, help="NPC display name")
    parser.add_argument("--pos", type=str, default=None, help="Static position x,y,z")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output path")
    parser.add_argument("--distance", "-d", type=float, default=6.0, help="Distance (default: 6.0)")
    args = parser.parse_args()

    if args.npc_name is None and args.pos is None:
        parser.error("Provide either npc_name or --pos")

    if args.pos:
        parts = [float(v) for v in args.pos.split(",")]
        if len(parts) != 3:
            parser.error("--pos must be x,y,z")
        x, y, z = parts
        label = f"({x:.0f},{y:.0f},{z:.0f})"
        code = build_pos_capture_code(x, y, z, args.distance)
        if args.output is None:
            args.output = Path(f"screenshots/pos-{x:.0f}-{y:.0f}-{z:.0f}.png")
    else:
        label = args.npc_name
        code = build_npc_capture_code(args.npc_name, args.distance)
        if args.output is None:
            safe = args.npc_name.lower().replace(" ", "-").replace("'", "")
            args.output = Path(f"screenshots/{safe}.png")

    print(f"Capturing {label} at {args.distance}m...")
    asyncio.run(capture(code, label, args.output))


if __name__ == "__main__":
    main()
