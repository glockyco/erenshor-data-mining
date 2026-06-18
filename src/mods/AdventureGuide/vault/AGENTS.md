# Erenshor Vault Publishing Notes

Adventure Guide is distributed through the Erenshor Vault (erenshorvault.app),
which hosts Lunaris mods that players install through Lunaris' mod management
UI. Thunderstore/BepInEx packaging has been retired.

## Listing source of truth

`vault.toml` holds the create-mod fields (name, slug, short description, tags,
source URL). `README.md` is the full description (markdown), `CHANGELOG.md` the
per-version notes, `icon.png` the logo. Tag slugs in `vault.toml` resolve to tag
UUIDs via `GET https://erenshorvault.app/api/tags`.

## Package contents

The Vault package is a zip with `adventure-guide/manifest.json` plus the plugin
assembly. Ship ONLY `AdventureGuide.dll` — Lunaris provides ImGui.NET,
Newtonsoft.Json, and System.Numerics.Vectors, so no dependency DLLs are bundled
(verified against AmarionCodex's published package, whose `containedFiles` is
just its own DLL). Build it with:

```bash
uv run erenshor mod build --mod adventure-guide
# output: src/mods/AdventureGuide/bin/Debug/netstandard2.1/AdventureGuide.dll
```

## Version numbers

Versions are `YYYY.MDD.R` (e.g. `2026.618.0`): year, month (no leading zero) +
zero-padded day, then a per-day revision starting at 0. This is the same CalVer
the in-DLL `PluginInfo.Version` uses (`scripts/generate-mod-version.py`), and it
satisfies the Vault's required `x.y.z` (three numeric segments) format.

For a second release on the same day, bump the revision: check the latest
version at `GET https://erenshorvault.app/api/mods/adventure-guide/versions` and
increment the third segment. Keep the `CHANGELOG.md` top heading equal to the
uploaded version.

## Uploading

The Vault's write API (the Personal Access Token, "CLI access to upload and
manage your mods") is not available yet — the Public API Key is read-only. Until
the PAT ships, upload manually:

1. erenshorvault.app/new-mod — create the entry from `vault.toml` + `README.md`
   + `icon.png` (first release only).
2. Versions -> new — select `AdventureGuide.dll` as the main file, add NO asset
   files (the form builds the zip + manifest), set the version, and paste the
   `CHANGELOG.md` entry.

Once the PAT API ships, an `erenshor mod vault` command can read `vault.toml`
and automate `POST /api/mods` + `POST /api/mods/{mod_ref}/versions` with an
`Authorization: Bearer <token>` header.
