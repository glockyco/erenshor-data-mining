# Erenshor Vault Publishing Notes

Adventure Guide's native Lunaris build is distributed through the Erenshor
Vault (`erenshorvault.app`), whose mod manager installs it through Lunaris.
The separate native BepInEx build is packaged and published on Thunderstore.

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
uv run erenshor mod build --mod adventure-guide --loader lunaris
# output: src/mods/AdventureGuide/bin/Debug/netstandard2.1/lunaris/AdventureGuide.dll
```

## Releasing

`uv run erenshor mod vault --mod adventure-guide` prepares a release:

- Derives the next version `YYYY.MDD.R` from the Vault
  (`GET /api/mods/adventure-guide/versions`), incrementing the revision when
  today's date prefix already exists — no hand-edited patch numbers.
- Bakes that version into the DLL via `-p:ModVersion`, so `PluginInfo.Version`
  (and the `[LunarisPlugin]` attribute Lunaris reads) matches what you publish.
  This matters: Lunaris compares the installed attribute version against the
  Vault's latest by semver and, on update, overwrites its stored version with
  the DLL's — so a stale in-DLL version causes a perpetual "update available".
- Verifies `CHANGELOG.md` leads with the same version.
- Prints the version and the upload steps.

The `YYYY.MDD.R` format (year, month without leading zero + zero-padded day,
per-day revision) satisfies the Vault's required three-segment `x.y.z`.

## Uploading

The Vault's write API (the Personal Access Token, "CLI access to upload and
manage your mods") is not available yet — the Public API Key is read-only. Until
the PAT ships, `mod vault` builds the DLL with the right version and you upload
manually:

1. erenshorvault.app/new-mod — create the entry from `vault.toml` + `README.md`
   + `icon.png` (first release only).
2. Versions -> new — select `AdventureGuide.dll` as the main file, add NO asset
   files (the form builds the zip + manifest), set the version `mod vault`
   printed, and paste the `CHANGELOG.md` top entry.

When the PAT API ships, the upload step (`POST /api/mods/{mod_ref}/versions`
with an `Authorization: Bearer <token>` header) slots into `mod vault` — the
version derivation and build are already in place.
