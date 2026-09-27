## Context

See proposal.md - Why. `_derive_group_rarity` in the clean build computes `is_unique` from the count of ordinary spawn placements and falls back to the prefab flags when a character has none, which is how event bosses end up as Enemy. The wiki generator, the Lua data exporters, the map queries and the spawn-points sheet each read `is_unique`, `is_rare`, and `is_common` and apply their own precedence.

## Decisions

**The tier is computed once, in the clean build.** The processor already groups duplicate characters and collects their spawns, so it has every input. Consumers read `encounter_tier`. Alternative: a SQL view. Rejected, because the rule needs the effective BossXp and the placement count per deduplication group, which the processor already has.

**The level-40 rule is applied, not only the prefab value.** `NPC.Start` sets BossXp to 2 for every NPC at level 40 or above, so the prefab value understates the game's own classification. The rule and the consider-text threshold are pinned as code facts, and the processor carries the matching consumer tags.

**Placement count separates boss from elite.** A named character that the game can place at several spawn points at once is a roaming encounter, not a boss. A single placement or an event-only spawn is a fixed encounter.

**Character-level rarity columns go.** `character_spawns.is_rare` stays, because it is a per-placement game fact that the guide and the spawn popups show next to the spawn chance.

**Live markers use the stored tier by name.** The companion mod reports `boss` for BossXp above 1 and cannot know placement counts. The map looks the live entity's name up in the characters it already has, and uses the mod's value only for names it does not know.

## Risks / Trade-offs

- Wiki pages lose the Rare type → the spawn tables already show the chance per placement, which is the information a reader needs.
- Category:Elites does not exist on the wiki → it has to be created on deploy; the deploy summary names it.
