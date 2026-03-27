# Thunderstore Publishing Notes

## Version numbers

Versions follow `YYYY.MDD.R` CalVer. **Never guess the version** — derive it:

```bash
uv run erenshor mod thunderstore --mod adventure-guide --dry-run
```

The deploy script queries the Thunderstore API and prints the computed version.
It starts revision at `.0` when today's date hasn't been published yet, and
increments if it has. The dry-run output line looks like:

```
  Version: 2026.327.0
```

Use that exact string for the changelog heading.

## Changelog format

Thunderstore requires `## vX.Y.Z` version headers to activate the Changelog tab.
Plain headings like `## Initial Release` are not recognised and leave the tab greyed out.

The CHANGELOG.md must also be added via `[[build.copy]]` in `thunderstore.toml` —
tcli does not include it automatically despite the `changelog =` field in `[build]`.

## Files in this directory

`AGENTS.md` is not included in the published package. tcli only packages files
listed in `[[build.copy]]` plus `icon.png`, `README.md`, and `manifest.json`.
