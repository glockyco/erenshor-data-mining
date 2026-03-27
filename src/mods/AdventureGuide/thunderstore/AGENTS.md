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

## Writing changelog entries

**Audience:** entries are for mod users (players), not developers. Describe what
changed from the player's perspective — what they see, find, or can now do — not
how it was implemented.

**Include:**
- New features a player encounters in-game
- Bug fixes that affect what a player sees or interacts with
- Behaviour changes a player would notice

**Exclude:**
- Internal refactoring or code restructuring
- Data pipeline or build system changes
- Test updates
- Anything a player cannot observe in-game

**How to write:** One clause. No connectives (no dashes, no semicolons, no
"—"). Either "Fixed X" or "X now does Y". No jargon, no commit hashes, no
file names. Match the length of existing entries — if yours is noticeably longer,
cut it. Avoid "Improved": it is almost always too vague.

**Examples:**

| Bad (developer-focused) | Good (player-focused) |
|---|---|
| Fixed is_map_visible predicate not being applied to guide queries | Fixed certain quests being hidden from the guide |
| Filtered duplicate NPC rows caused by unused prefab entries in source data | Fixed quest givers sometimes appearing multiple times on the same quest |
| Added fallback rendering path for quests with UNKNOWN completion type | Quests with incomplete data now show partial steps |

## Files in this directory

`AGENTS.md` is not included in the published package. tcli only packages files
listed in `[[build.copy]]` plus `icon.png`, `README.md`, and `manifest.json`.
