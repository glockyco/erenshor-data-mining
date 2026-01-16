# Game DLLs

This directory contains game assemblies required for mod compilation. These
files are **not committed** to the repository.

## Setup

Run the setup command to copy DLLs from your game installation:

```bash
uv run erenshor mod setup
```

This requires either:
- `ERENSHOR_GAME_PATH` environment variable set to your game installation
- Game files downloaded via `uv run erenshor extract download`

## Required Files

- `Assembly-CSharp.dll` - Game code
- `UnityEngine.dll` - Unity engine
- `UnityEngine.CoreModule.dll` - Unity core module

## Why Not Committed

Game DLLs are copyrighted and cannot be redistributed. Each developer must
copy them from their own game installation.
