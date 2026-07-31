---
title: Quest Article Strategy
type: spec
status: draft
created: 2026-07-31
parent: 2026-07-09-erenshor-planning-overview
---

# Quest Article Strategy

**Decision: quest article conversion is deferred.** It is explicitly out of scope for
`2026-07-11-wiki-article-cutover`. No quest page is converted until the question below
is answered, because converting first would destroy the thing we would then have to
recreate.

**The question:** the pipeline can generate structured, step-by-step quest guides from
the clean database. The wiki's quest pages are mostly hand-written prose. Generated
instructions are more complete and more consistent. Human prose reads better and
carries knowledge no export contains. Neither replaces the other, and the right
combination is not obvious.

**What is not deferred.** `Quest` stays in the entity registry, `Template:Quest` still
gets its dual-path body, and `Module:Erenshor/Data/Quests` still deploys. The 19 pages
already using `{{Quest}}` keep working. Only conversion of the remaining corpus waits.

## Why this cannot be decided casually

### The corpus is mostly human writing, by multiple authors

`Category:Quests` holds 115 members, one of which is the `Quests` index. Only 19
transclude `{{Quest}}`. **96 pages carry no infobox at all.** They range from 446 bytes
(`The Curator`) to 6,404 bytes (`Mystery of Bellwain Island`), clustering around 0.5 to
1.3 KB with a long tail above 2 KB.

An authorship sample of five pages found **eight distinct editors**, and every sampled
page had been edited by more than one account: Pohjola, Jerigord, Amichai, Roan,
Azure Fang, Ulor, Biridian, Kezeal. This is accumulated community labour, not
scaffolding.

### Generation is strong, which is what makes the choice hard

The naive assumption is that generated guides would be thin. They are not. The Adventure
Guide pipeline produces two artifacts: `erenshor guide compile` writes the dense
`quest_guides/guide.json`, and the mod export writes
`quest_guides/quest-guide.json`, the stable wrapper consumed by the Adventure Guide mod
and embedded as a resource by its `GuideData.Load`. The latter is the quest-facing one,
and it holds 206 entries:

| Field | Entries carrying it |
|---|---|
| `rewards` | 206 |
| `steps` | 200 |
| `level_estimate` | 200 |
| `zone_context` | 199 |
| `description` | 196 |
| `completion` | 187 |
| `required_items` | 174 |
| `acquisition` | 107 |
| `chain` | 53 |
| `prerequisites` | 25 |

Step-count distribution: 6 entries with no steps, 18 with one, 69 with two, 66 with
three, 18 with four, 10 with five, 12 with six, and a tail to twelve. Only 24 of 206
would produce a near-empty page. Measured directly against the tables, all 191
wiki-generated quests carry at least one structured fact among acquisition, required
items, completion, or giver role, so emptiness comes from missing *step edges* rather
than missing data.

A real generated entry, verbatim and abridged:

```json
{
  "display_name": "Secure Port Azure",
  "description": "Keep your eyes open for any intel on how or why Sivakayans are
    gaining access to Port Azure. Share it with Guard Captain Kilkay if you find it.",
  "quest_type": "fetch",
  "zone_context": "Port Azure",
  "steps": [
    { "order": 1, "action": "collect",
      "description": "Collect Ealdred's Journal.",
      "target_name": "Ealdred's Journal", "quantity": 1,
      "level_estimate": { "recommended": 32,
        "factors": [ { "source": "drop", "name": "Darkwarden Ealdred", "level": 32 } ] } },
    { "order": 2, "action": "turn_in",
      "description": "Turn in items to Captain Kilkay.",
      "target_name": "Captain Kilkay",
      "level_estimate": { "recommended": 38, "factors": [ … ] } }
  ],
  "rewards": { "xp": 1000, "gold": 1000 },
  "chain": [ { "quest_name": "Sivakayan Intel for Kilkay (1)", "relationship": "previous" } ]
}
```

That is a usable walkthrough. The problem is not quality. It answers different
questions than the prose does.

### Three categories of content, not two

This is the distinction a future session should reason from. The split is not
"generated versus human". It is three-way, and the middle category is the interesting
one.

**1. Generated today.** Ordered steps, collect and turn-in targets, required items and
where they drop, recommended levels derived from source-mob levels, rewards, zone
context, quest chains, prerequisites.

**2. Present in the data, not surfaced anywhere.**

- **Reputation consequences.** `quest_faction_affects` holds 107 rows of
  `faction_stable_key` and `modifier_value`. The human sentence "Completing stage 1 of
  this quest may drop your reputation with the Azure Guard to hostile levels" is
  derivable, and is not currently emitted.
- **The dialogue prompt keyword.** `character_dialogs.keywords` joined on
  `assign_quest_stable_key` resolves the exact word a player must say. **62 of 191
  quests** have one for acquisition, 8 for completion. For `A Bounty on Guard Captain
  Kilkay` the row is `character:ripper demerth`, keyword `Kilkay`, which is exactly the
  green `[Kilkay]` span a human typed by hand.
- **Repeatability and destructive turn-in behaviour.** `quest_variants` carries
  `repeatable`, `kill_turn_in_holder`, `destroy_turn_in_holder`, `drop_invuln_on_holder`,
  `once_per_spawn_instance`, `disable_text`, `dialog_on_success`, and
  `dialog_on_partial_success`.

A meaningful share of what looks like irreplaceable human writing is unwired data. The
decision should be taken *after* wiring category 2, because doing so moves the boundary.

**3. Not in any data, and not derivable.** Verbatim from live pages:

- `A Bounty on Guard Captain Kilkay` — "Completing stage 1 of this quest may drop your
  reputation with the Azure Guard to hostile levels. Part 2 carries no reputation
  changes." The second sentence is human judgement about a chain, not a row.
- `Sivakayan Ore` — "Although this quest can be obtained quite early, the Sivakayan
  enemies players need to defeat to obtain the ore are quite powerful and may pose a
  challenge for players until later in the game. As such, players may wish to wait…"
- `The Mathers' Demise` — "Be careful not to lose the Old Church Key, as there is
  currently no known way to obtain another."
- `The Dark Flame` — "Completing both [[The Dark Flame]] and [[The Life Flame]] will
  cause [[The Abomination]] to permanently spawn…"
- `Willow Seeds` — "This quest does not appear in your journal."
- `Whispers of Wyland` — "Alternatively you can speak to [[Revan Gavault]] at the altar
  and he will mistaken you for [[Wyland]]…"
- `The Lunchbag` — "Octorunners are most commonly found at night off the coast of the
  [[Braxonian Desert]]."

Difficulty judgement, irreversibility warnings, emergent cross-quest consequences,
alternative solution paths, farming advice, and knowledge that the game's own UI omits
something. None of it is exportable. All of it is why players read the wiki.

### One quest does not equal one page

Entity granularity and page granularity disagree. This is a modelling problem, not
naming drift.

- The DB models `A Dying Wish` as four entities, `Part 1` through `Part 4`. The wiki has
  **one** page, `A Dying Wish (Quest)`, 5,747 bytes, covering the whole chain.
- Other part-suffixed DB entities: `A Lost Portal Pt. 2`, `Repairing Orion's Ring,
  Part 2`, `Sivakayans in Port Azure Pt. 2`, `The Loss Stone Pt. 2`, `The Lunchbag Pt. 2`.
  Some have matching live pages, some do not.
- Several DB quests already share one `wiki_page_name` deliberately: `The Mathers'
  Demise`, `The Lost Soul`, `The Mystery of Bellwain Island`, `Ripper's Questline`,
  `Sivakayan Intel for Kilkay`, `Soluna's Celestial Blade`, `Whispers of Wyland`.

191 wiki-generated quest rows map to 179 distinct page names, and the wiki consolidates
further still. A converter that assumes one stanza per entity per page will fight the
corpus.

### The data has no ordered-stage model

`quest_variants` has 201 rows and 22 columns, and `Quest.cs` confirms the same shape.
There is **no stage, order, or prompt field anywhere in the quest tables.** The ordered
`steps` in the generated guide are inferred by `edge_builder`, which derives talk, kill,
travel, read, and shout edges from character, zone, and item relationships. Alternatives
for required items, acquisition, and completion are OR-grouped rather than sequenced.

That matters for the decision: generated ordering is an inference the pipeline makes,
not a fact the game exports, so a generated walkthrough's step order is a modelling
opinion that a human may legitimately disagree with.

### The Adventure Guide already chose an answer, and it is a modest one

The mod embeds the wrapper, indexes quests, and renders acquisition, turn-in,
description, and objectives, navigating only typed generated steps. When `steps` is
absent it displays `No guide data available for this quest.` rather than improvising.

That is a reasonable in-game contract and a poor wiki contract. A companion overlay may
say nothing for a quest it cannot describe. A wiki page that says nothing is worse than
the prose page it replaced. The mod's precedent therefore does not transfer, and the
wiki needs its own answer for thin quests.

### Coverage does not line up either

- **75 DB page names have no live page.** Examples: `A Dying Wish, Part 1` through
  `Part 4`, `A Fernallan Rune`, `A Solunarian Rune`, `A Vithean Rune`, `An Arena Token`,
  and many `Crafting:*` entries.
- **11 live pages have no DB match.** Mostly title drift: `A Dying Wish (Quest)`,
  `Catnip for a Statue` against DB `Catnip for a statue` (case only), `Meet The
  Fisherman` against `Meet the Fisherman`, `Serra Stiles Shovel` against `Serra Stile's
  Shovel`, `Faerie Dust for Nylith Valarro` against DB `Valorro` (a spelling difference
  in the game data). Plus the `Quests` index page itself.

Most are fixable through `mapping.json`. `A Dying Wish` is not, because it is the
granularity problem wearing a disambiguation suffix.

### There is no existing annotation layer to build on

`quest_guides/graph_overrides.toml` contains exactly 26 `[[edges]]` records. All are
unlocks, requirements, and chain edges connecting doors, items, quests, characters, and
zone lines. **There is no prose, no dialogue text, and no human-authored annotation
surface anywhere in the pipeline.** Whatever annotation model gets chosen is built from
nothing.

## Candidate approaches

None chosen. Each is listed with the tradeoff that actually decides it.

**A. Leave quest pages entirely human.** Generated data appears only in a small infobox,
as `{{Quest}}` already does on 19 pages. *For:* zero content risk, no new machinery,
community keeps ownership. *Against:* 75 quests never get a page, the guide data stays
invisible on the wiki, and pages drift from the game on every patch.

**B. Formalise the conventions editors already invented.** The corpus has converged on
recurring idioms: a green `<span style="color: #15e300;">[keyword]</span>` prompt, a red
consequence or repeatability callout, a stage wikitable with `Stage`/`Name`/`Description`,
and a "Total Rewards" table with EXP, gold, items, and repeatability. Turn those four
into templates fed by generated data and leave the numbered walkthrough and Notes
sections human. *For:* the seam already exists in the corpus, so it is the lowest-friction
partial automation, and it consumes category 2 directly. *Against:* needs per-page human
placement, so it does not create the 75 missing pages.

**C. Generated body with human annotation slots.** The page is generated from guide data
with named slots a human fills for warnings, strategy, and alternatives, surviving
regeneration the way `{{ItemSource}}` rows are meant to. *For:* every quest gets a page,
data stays fresh, human knowledge becomes first-class rather than incidental. *Against:*
the most machinery, needs a preservation guarantee as strong as the thin-page converter,
and migrating 96 prose pages into slots is largely manual and lossy if rushed.

**D. Two surfaces.** A generated reference page per quest plus the human walkthrough
page, cross-linked. *For:* no migration risk, both audiences served. *Against:* splits
reader attention, duplicates titles, and creates a permanent consistency burden between
two pages about the same quest.

## What must be decided

1. Is a quest page primarily a **walkthrough** or a **data reference**? Every other
   answer follows from this one.
2. What is the page unit, given that one DB quest is not one page? Chain-level pages,
   entity-level pages, or a declared mapping.
3. Which of the three content categories may a bot write, and which is human-only?
4. How does human content survive regeneration, and what is the preservation guarantee?
5. What happens to the 75 quests with no page today?
6. Who resolves the 11 title mismatches, through `mapping.json` or page moves?
7. Is inferred step ordering trustworthy enough to publish, given the game exports no
   stage model?

## Preconditions before deciding

- **Wire category 2 first.** Surface `quest_faction_affects`, the dialogue keyword for
  the 62 quests that have one, and the `quest_variants` behaviour flags into the guide
  output. Until that lands, the generated-versus-human boundary sits in the wrong place
  and the decision would rest on stale evidence.
- **Finish at least one cutover slice.** Stances and zones prove the machinery, and
  quest conversion needs the override classifier to stop skipping multi-key pages as
  ambiguous, which slice 3 forces anyway.
- **Read the corpus properly.** The 15-page sample behind this document is indicative,
  not exhaustive. A decision session should read all 96.

## Meanwhile

- Do not convert quest pages.
- Do not delete or rewrite hand-written quest prose.
- Do not remove `Quest` from the entity registry or stop deploying
  `Module:Erenshor/Data/Quests`.
- Fix the trivial title mismatches through `mapping.json` when convenient. They are
  independent of this decision and reduce noise for whoever picks it up.
