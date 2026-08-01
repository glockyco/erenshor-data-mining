---
title: Wiki Legacy Article Cutover
type: plan
status: draft
created: 2026-07-11
parent: 2026-06-04-wiki-cargo-data-architecture
---

# Wiki Legacy Article Cutover

Convert production articles to exact `lua=1` one entity type at a time after the
shared Lua/Cargo foundation is complete. This plan owns guarded article conversion,
per-type proof, rollback, legacy-branch removal, and Jinja retirement only.

> **Quest article conversion is excluded.** It remains deferred until
> `2026-07-31-wiki-quest-article-strategy` is approved. `Template:Quest` and
> `Module:Erenshor/Data/Quests` remain foundation-supported, and existing quest pages
> may participate in sandbox parity. This plan never adds `lua=1` to a quest article.

## Preconditions

The first precondition is an approved passing foundation-completion report from
`2026-08-01-wiki-cargo-cutover-foundation`. The report must prove all required parity
cases passed, every required Cargo table and data module exists with headroom,
production drift is zero, rollback artifacts exist, and zero production articles
were converted. This plan remains `draft` until that report permits activation.

The foundation owns schema revision, module sizing and deployment, first production
Cargo creation, all-seven selector preparation, TemplateSandbox infrastructure, and
generic deployment-safety implementation. None of that work is repeated here.

## Conversion invariants

- Exact `lua=1` selects the generated Lua/Cargo branch. `stablekey` identifies the
  entity after selection.
- Every write uses guarded base-revision checks and fails closed on drift.
- Generated-duplicate parameters are removed.
- Divergent overrides, the `-` sentinel, unknown parameters, and non-template
  community sections survive conversion.
- Every legacy template stanza is recognized and accounted for before a page is
  edited.
- A multi-entity page contains exactly the authoritative ordered
  `(entity_type, stablekey)` set for its title.
- The bot performs no deletion. Orphan deletion remains a manual admin operation.
- Rollback refuses any page whose remote revision differs from the deployed revision
  recorded in the manifest.
- A type's legacy branch and Jinja generator are retired only after complete identity
  and content coverage for that type. Shared Spell/Skill retirement waits for both
  types.

## Stop conditions

Every task below stops before its first article edit on any parity failure, repository
or live drift, protection failure, unresolved identity, unrecognized stanza, changed
remote revision, missing expected Cargo row, or missing rollback artifact. Once a
batch starts, the same condition stops the batch. A failed page is never skipped to
claim completion. It prevents retirement of the entire type until resolved and
reverified.

## Tasks

### Stance

- [ ] Run the legacy and exact `lua=1` Stance sandbox parity case. Generate and review
  the guarded conversion report, then convert one Stance page with `lua=1`. Verify its
  exact `Stances` row and the reverse query through `Skills.StanceToUseKey`. Prove
  guarded rollback and reapply on that canary. Convert the remaining six pages and
  verify seven-of-seven identity and preserved-content coverage. In a separate
  commit, remove only the Stance legacy branch and retire only the Stance Jinja
  generator.
  - **Canary commands:**
    ```bash
    uv run erenshor -V playtest wiki articles preflight --type stance
    uv run erenshor -V playtest wiki articles convert --type stance --dry-run
    uv run erenshor -V playtest wiki articles convert --type stance --apply --limit 1 --assert-user WoWBot
    uv run erenshor -V playtest wiki verify
    uv run erenshor -V playtest wiki articles rollback <stance-canary-manifest>
    uv run erenshor -V playtest wiki articles convert --type stance --apply --limit 1 --assert-user WoWBot
    ```
  - **Batch and retirement commands:**
    ```bash
    uv run erenshor -V playtest wiki articles convert --type stance --apply --assert-user WoWBot
    uv run erenshor -V playtest wiki articles preflight --type stance
    uv run erenshor -V playtest wiki verify
    ```

### Zone

- [ ] Repeat guarded sandbox parity, report review, one-page canary, rollback, reapply,
  batch conversion, complete coverage, and per-type retirement for all 43 generated
  Zone pages. Verify reverse queries against `ObtainedFrom` and `Spawns`. Do not add a
  Zone detail table. Remove the Zone legacy branch and Zone Jinja generator only after
  all 43 authoritative pages pass.
  - **Commands:**
    ```bash
    uv run erenshor -V playtest wiki articles preflight --type zone
    uv run erenshor -V playtest wiki articles convert --type zone --dry-run
    uv run erenshor -V playtest wiki articles convert --type zone --apply --limit 1 --assert-user WoWBot
    uv run erenshor -V playtest wiki verify
    uv run erenshor -V playtest wiki articles rollback <zone-canary-manifest>
    uv run erenshor -V playtest wiki articles convert --type zone --apply --assert-user WoWBot
    uv run erenshor -V playtest wiki articles preflight --type zone
    uv run erenshor -V playtest wiki verify
    ```

### Spell and Skill

- [ ] Require the foundation's byte-faithful adoption of live `Template:Ability`.
  Run sandbox parity for both generated types. Convert one single-type canary and one
  page containing both a Spell stanza and a Skill stanza. Prove separate `Spells` and
  `Skills` rows, shared `AbilityClasses` rows where expected, preserved ordered
  identities, content preservation, rollback, and reapply. Convert the complete
  approved Spell and Skill corpus. Retire the shared Ability legacy path and both
  Jinja generators only after both types have complete coverage.
  - **Commands:**
    ```bash
    uv run erenshor -V playtest wiki articles preflight --type spell
    uv run erenshor -V playtest wiki articles preflight --type skill
    uv run erenshor -V playtest wiki articles convert --type spell --dry-run
    uv run erenshor -V playtest wiki articles convert --type skill --dry-run
    uv run erenshor -V playtest wiki articles convert --type spell --apply --limit 1 --assert-user WoWBot
    uv run erenshor -V playtest wiki articles convert --page <spell-skill-page> --apply --assert-user WoWBot
    uv run erenshor -V playtest wiki verify
    uv run erenshor -V playtest wiki articles rollback <ability-canary-manifest>
    uv run erenshor -V playtest wiki articles convert --type spell --apply --assert-user WoWBot
    uv run erenshor -V playtest wiki articles convert --type skill --apply --assert-user WoWBot
    uv run erenshor -V playtest wiki verify
    ```

### Character

- [ ] Require the deployed Character data module to retain at least 25 percent size
  headroom below 4,194,304 bytes. Run sandbox parity and a guarded Character canary.
  Prove the exact `Characters`, `Spawns`, and `CharacterAbilities` rows plus forward
  and reverse queries. Prove preserved content, rollback, and reapply. Convert the
  approved Character corpus, verify complete identity and content coverage, then
  remove the Character legacy branch and retire Character Jinja generation in a
  separate commit.
  - **Commands:**
    ```bash
    uv run erenshor -V playtest wiki articles preflight --type character
    uv run erenshor -V playtest wiki articles convert --type character --dry-run
    uv run erenshor -V playtest wiki articles convert --type character --apply --limit 1 --assert-user WoWBot
    uv run erenshor -V playtest wiki verify
    uv run erenshor -V playtest wiki articles rollback <character-canary-manifest>
    uv run erenshor -V playtest wiki articles convert --type character --apply --assert-user WoWBot
    uv run erenshor -V playtest wiki articles preflight --type character
    uv run erenshor -V playtest wiki verify
    ```

### Item

- [ ] Require the revised `ObtainedFrom`, `UsedIn`, and `ItemEffects` schemas. Run
  sandbox parity and one guarded Item canary while preserving the production
  equipment tooltip path. Prove the exact `Items` and owned relationship rows,
  reverse queries, preserved content, rollback, and reapply. Convert the approved
  Item corpus, verify complete identity and content coverage, then remove the Item
  legacy branch and retire Item Jinja generation last.
  - **Commands:**
    ```bash
    uv run erenshor -V playtest wiki articles preflight --type item
    uv run erenshor -V playtest wiki articles convert --type item --dry-run
    uv run erenshor -V playtest wiki articles convert --type item --apply --limit 1 --assert-user WoWBot
    uv run erenshor -V playtest wiki verify
    uv run erenshor -V playtest wiki articles rollback <item-canary-manifest>
    uv run erenshor -V playtest wiki articles convert --type item --apply --assert-user WoWBot
    uv run erenshor -V playtest wiki articles preflight --type item
    uv run erenshor -V playtest wiki verify
    ```

## Shared verification

Run local conversion and preservation coverage before each slice:

```bash
uv run pytest tests/unit/application/wiki_deploy/test_article_identity.py \
  tests/unit/application/wiki_deploy/test_override_classifier.py \
  tests/unit/application/wiki_deploy/test_override_migration.py \
  tests/unit/application/wiki_deploy/test_pages.py \
  tests/unit/application/wiki_deploy/test_manifest.py \
  tests/unit/application/wiki_deploy/test_rollback.py
uv run python wiki-dev/import_pages.py --dry-run
uv run python wiki-dev/import_pages.py
uv run python wiki-dev/smoke_test.py
uv run python wiki-dev/parity_check.py
uv run python wiki-dev/cargo_check.py
```

Run the foundation-provided TemplateSandbox parity command for the target type before
each canary. Its deterministic report must contain zero `failed` and zero required
`not_exercised` cases. Then use `wiki articles preflight` and `convert --dry-run` to
review generated-duplicate removal, retained divergent overrides, retained `-`
sentinels, unknown parameters, non-template sections, every recognized stanza, and
the exact authoritative identity set.

For every live canary and batch, `wiki verify` must establish exact source SHA,
rendered parity, expected Cargo rows and reverse queries, completed forced-link and
Cargo refresh, unchanged preserved content, and an available rollback sidecar. The
rollback command must refuse a deliberately changed remote revision before the clean
canary rollback is accepted.

## Completion

This plan is complete only when Stance, Zone, Spell and Skill, Character, and Item have
full approved corpus coverage and their per-type retirement gates pass. Quest remains
unconverted. No community-row implementation, schema foundation work, first table
creation, broad identity-registry rollout, or generic deploy-safety implementation is
part of this plan.
