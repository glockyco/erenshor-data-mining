---
title: Dynamic Spawn Semantics and Map UX Audit
type: plan
status: active
created: 2026-07-11
parent:
superseded_by:
archived:
---

# Goal

Make dynamic-only character rarity and Brax spawn provenance authoritative so
the processor and its map/wiki consumers identify bosses without inferring
rarity from event placement count or collapsing conditional references.

## Current state

- `src/erenshor/application/processor/characters.py::_derive_group_rarity`
  excludes event summons when ordinary placements exist, but dynamic-only
  groups still fall back to raw `IsUnique`/`IsRare` flags. In the playtest
  data, Astra, Demented Malaroth, and Shivunax each have one dynamic spawn and
  clean `is_unique=0`, `is_rare=0`; no authoritative rarity override currently
  covers these entries.
- Wiki character rendering maps `is_unique` to the Boss classification, so
  dynamic-only rarity decisions affect every generated character surface.
- `BraxFightEvent.CheckIn` consumes `BraxSpawn` and disables
  `GodBraxRestored`; `ResetEvent` enables the restored object. The dynamic-spawn
  catalog intentionally treats `GodBraxRestored` as a `SetActive` toggle rather
  than an instantiate field.
- `PlaneOfBrax` serializes ordinary `BraxSpawn (6)` at
  `(2521.9, 75.6, 381.3)`, ordinary `BraxSpawn` at
  `(2530.1, 75.6, 404.0)`, and inactive `God Brax Restored` at
  `(2543.6, 75.5, 404.1)`. Clean output currently reports the first ordinary
  row disabled, the second enabled, and the restored reference as a separate
  direct placement marked unique; the runtime relationship and provenance are
  not represented together.

## 1. Dynamic unique / boss classification

- [ ] Audit every dynamic-only character with explicit prefab rarity flags,
      including Astra, Demented Malaroth, Shivunax, Brax, and other
      single-spawn candidates.
- [ ] Trace unique/boss and rare/common outcomes to explicit game metadata or
      an approved mapping rule, never dynamic spawn cardinality.
- [ ] Add focused processor and map/wiki regressions for unique, rare, common,
      and mixed ordinary/dynamic groups.
- [ ] Record intentional exceptions in the authoritative mapping or catalog.

## 2. Brax active-versus-unused provenance

- [ ] Trace both `Brax, God of Elements` references through the shipped
      `BraxFightEvent`, serialized prefabs, scene placements, and event fields.
- [ ] Determine whether each reference can be active in normal play, requires a
      quest/event state, or is an unused/duplicate asset.
- [ ] Represent active spawn semantics and conditional state explicitly,
      preserving both ordinary coordinates and the restored reference without
      inventing availability percentages.
- [ ] Add a regression covering the final classification, active/conditional
      provenance, and all three PlaneOfBrax coordinates.

## Acceptance criteria

- [ ] Dynamic-only character groups receive explicit, evidence-backed
      unique/boss or rare/common classifications.
- [ ] Brax references have a documented active, conditional, or unused
      determination and retain their source coordinates.
- [ ] No consumer presents the two ordinary Brax rows as simultaneously active
      bosses when the shipped event state says otherwise.
