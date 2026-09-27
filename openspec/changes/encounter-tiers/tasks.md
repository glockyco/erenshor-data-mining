## 1. Clean database

- [ ] 1.1 Pin the level-40 BossXp rule (`NPC.Start`) and the consider-text threshold (`PlayerControl.ConsiderOpponent`) as assert code facts, and verify `extract code-facts` passes.
- [ ] 1.2 Compute `encounter_tier` per deduplication group, write it, and remove `is_unique`, `is_rare`, and `is_common` from the clean `characters` table. Verify with unit tests for each spec scenario and with `extract build`: Shivunax boss, Alpha Wolf elite, Grizzlepaw boss.

## 2. Consumers

- [ ] 2.1 Wiki: type field, categories, Lua data exporters, `Character.lua`, and `Character.wiki` read the tier. Verify with generator tests and Lua testcases.
- [ ] 2.2 Map: queries, labels, colours, filters, sort order, and live-marker styling read the tier. Update the fixture schema. Verify with `erenshor maps check` and a browser check of a boss and an elite.
- [ ] 2.3 Sheets and golden query: the spawn-points sheet and the map golden query show the tier. Verify with the sheets tests.

## 3. Verification

- [ ] 3.1 Run `extract build`, `golden capture`, and review the baseline diff with the user.
- [ ] 3.2 Run `uv run erenshor test ci` and `openspec validate encounter-tiers --strict`.
