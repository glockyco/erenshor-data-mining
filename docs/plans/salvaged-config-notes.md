# Salvaged Notes from Deleted Skills

## Configuration (from `configuration` skill)

- **Two-layer config**: `config.toml` (tracked) + `.erenshor/config.local.toml` (gitignored, merges over project config). User-specific paths and credentials go in local config.
- **Variable expansion**: `$HOME`/`~` and `$REPO_ROOT` are expanded in path values.
- **Three variants**: main (2382520), playtest (3090030), demo (2522260) — each with completely separate databases, Unity projects, game downloads, wiki caches, logs, and Google Sheets spreadsheets. Layout: `variants/{variant}/`.
- **Use `resolved_*` methods** (not raw config values) for paths — e.g., `config.variants["main"].resolved_database(repo_root)` returns a `Path`; raw values contain unexpanded `$REPO_ROOT`.
- **Google Sheets credentials**: service account JSON at `~/.config/erenshor/google-credentials.json`, must have **Editor** (not Viewer) access to the spreadsheet.

## Debugging (from `debugging` skill)

- **Unity version pinned**: must be exactly 2021.3.45f2. Mismatch causes silent export failures.
- **Editor symlink**: exports require `variants/{variant}/unity/Assets/Editor` symlink to exist. Verify with `ls -la`.
- **ScriptableObject broken refs**: after game updates, assets may have broken references — run Unity in GUI mode to surface console errors.
- **StableKey duplicates**: if database has duplicate keys, investigate StableKey generation logic (not just data issues).
