---
title: Planar March Release Refresh
type: plan
status: active
created: 2026-07-12
parent: 2026-07-09-erenshor-planning-overview
---

# Planar March Release Refresh

## Context

Planar March is the game patch releasing Monday 2026-07-13, bringing the playtest data into the main release. The bulk item deploy is deferred until release because playtest stats are spoilers; an early partial deploy was reverted on 2026-07-12. See [Wiki Item Quality Tooltips](2026-07-12-wiki-item-quality-tooltips) for the tooltip architecture details.

## Prepared

- [x] All playtest images and filename redirects uploaded to the live wiki (soft-prepare).
- [x] MediaWiki:Gadget-erenshor.css manually updated by the maintainer (interface-protected page).
- [x] Tooltip rendering pipeline fixed and spiked live: 12 item pages (4 samples + one per item kind) verified as WoWBot.
- [x] Deploys switched to the WoWBot@erenshor-wiki bot-password account (`.erenshor/config.local.toml`).
- [x] Repo Lua modules and item data modules deployed from playtest build 24157014; quality gate `PLANAR_MARCH_ENABLED` remains false.

## Data refresh

- [ ] Update the main variant game install from Steam once the patch is live.
- [ ] Run extract export, extract code-facts, extract build for the main variant.
- [ ] Run the dynamic-spawn coverage gate before any deploys.
- [ ] Run golden capture and review diffs; run `uv run pytest`.

## Wiki deploy

- [ ] Re-run images process and images upload for any icons changed since the playtest build.
- [ ] `wiki fetch --force`, `wiki generate`, then deploy ALL article pages: items, characters, spells, skills, stances, the Weapons and Armor overview pages, and zone pages (new Plane zones need review before deploy).
- [ ] `deploy-repo-pages` with regenerated Lua data modules from the release build.
- [ ] Flip `PLANAR_MARCH_ENABLED = true` in `Module:Erenshor/Item/Quality` and deploy it.
- [ ] Verify live: equipment pages render 8 quality cards in progression order with green Improved sparkles; spot-check one page per item kind plus a character, spell, skill, stance, and zone page for parser errors.

## Other consumers

- [ ] Deploy Google Sheets for the main variant.
- [ ] maps build then maps deploy for the production maps website.
- [ ] Compile and publish the quest guide if game data changed it.
