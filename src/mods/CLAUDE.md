# CLAUDE.md - BepInEx Mods

This file provides guidance to Claude Code (claude.ai/code) when working with BepInEx mods in this directory.

## Overview

This directory contains BepInEx mods for Erenshor. These are C# plugins that run inside the game using the BepInEx mod loader framework.

## Project Structure

```
src/mods/
├── erenshor-mods.sln                    # Visual Studio solution file
├── InteractiveMapsCompanion/            # Interactive Maps companion mod
│   ├── InteractiveMapsCompanion.cs      # Main plugin class
│   ├── ConditionalLogger.cs             # Conditional logging utility
│   ├── interactive-maps-companion.csproj
│   ├── ILRepack.targets                 # Assembly merging configuration
│   ├── packages.config                  # NuGet dependencies
│   └── Properties/
│       └── AssemblyInfo.cs
└── (future mods here)
```

## Building the Mods

### Prerequisites

- **Mono**: Required for building .NET Framework 4.7.2 projects on macOS
  ```bash
  brew install mono
  ```
- **Game files**: Must have already run `uv run erenshor extract download` to download the main variant game files to `variants/main/game/`

### Build Commands

**Build in Debug mode:**
```bash
cd /Users/joaichberger/Projects/Erenshor/src/mods
xbuild erenshor-mods.sln /p:Configuration=Debug
```

**Build in Release mode:**
```bash
cd /Users/joaichberger/Projects/Erenshor/src/mods
xbuild erenshor-mods.sln /p:Configuration=Release
```

**Output location:**
- Debug: `InteractiveMapsCompanion/bin/Debug/InteractiveMapsCompanion.dll`
- Release: `InteractiveMapsCompanion/bin/Release/InteractiveMapsCompanion.dll`

### Known Build Issues

**ILRepack fails on macOS with xbuild:**
The ILRepack step (which merges Fleck and Newtonsoft.Json dependencies into the final DLL) currently fails with xbuild on macOS. However, the compilation itself succeeds and produces a working `InteractiveMapsCompanion.dll`.

**Workaround**: The unmerged DLL works fine for development and testing. For production releases, build on Windows using MSBuild, or manually run ILRepack after building.

## Interactive Maps Companion Mod

### What It Does

Broadcasts the player's real-time position and orientation via WebSocket (port 18584) for use with the interactive maps website at `src/maps/`.

### Architecture

**Main Plugin Class** (`InteractiveMapsCompanion.cs`):
- Inherits from `BaseUnityPlugin` (BepInEx base class)
- Runs a Fleck WebSocket server on `ws://0.0.0.0:18584`
- Tracks player GameObject transform via `GameObject.Find("Player")`
- Broadcasts position updates when player moves (throttled by `SendInterval` config)
- Only sends updates when position/rotation changes beyond threshold (0.001 units)

**WebSocket Protocol**:
```json
{
  "scene": "string",    // Current Unity scene name
  "x": float,           // Player position X
  "y": float,           // Player position Y
  "z": float,           // Player position Z
  "fx": float,          // Forward vector X
  "fy": float,          // Forward vector Y
  "fz": float           // Forward vector Z
}
```

**Configuration** (BepInEx config system):
- `Debug.EnableLogging` (bool, default: false) - Toggle all logging
- `Network.SendInterval` (float, default: 0.1) - Update frequency in seconds

**ConditionalLogger** (`ConditionalLogger.cs`):
Wrapper around BepInEx logging that respects the `EnableLogging` config setting.

### Dependencies

**Game References** (from `variants/main/game/`):
- `Erenshor_Data/Managed/Assembly-CSharp.dll` - Game code
- `Erenshor_Data/Managed/UnityEngine.dll` - Unity engine
- `Erenshor_Data/Managed/UnityEngine.CoreModule.dll` - Unity core
- `BepInEx/core/BepInEx.dll` - BepInEx mod loader
- `BepInEx/core/BepInEx.Preloader.dll` - BepInEx preloader

**NuGet Packages** (from `packages/`):
- `Fleck 1.2.0` - WebSocket server library
- `Newtonsoft.Json 13.0.3` - JSON serialization
- `ILRepack.Lib.MSBuild.Task 2.0.43` - Assembly merging (build-time)

### Path Configuration

All paths in `.csproj` and `ILRepack.targets` use relative paths from the project file location:

- Game assemblies: `../../../variants/main/game/`
- NuGet packages: `../../../packages/`

This ensures the build works regardless of where the repository is cloned.

## Adding New Mods

1. **Create new project directory** under `src/mods/`
2. **Add to solution**: Open `erenshor-mods.sln` and add the new project
3. **Configure references**: Point to game assemblies in `variants/main/game/`
4. **Add NuGet packages**: Use `packages/` directory for shared dependencies
5. **Update this file**: Document the new mod's purpose and architecture

## Deployment

The built DLL is deployed to Cloudflare Workers for distribution via the interactive maps website:

- Download URL: `https://erenshor-maps.wowmuch1.workers.dev/mods/InteractiveMapsCompanion.dll`
- Installation instructions: See `src/maps/src/routes/(app)/mod/+page.svelte`

## Notes

- **Do not commit build artifacts**: `bin/` and `obj/` are gitignored
- **Only mod source code is tracked**: Game assemblies are not in git (downloaded via extract pipeline)
- **Main variant only**: Mods currently only reference the main game variant, not playtest or demo
