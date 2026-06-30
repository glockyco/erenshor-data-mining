---
title: AEEvent Export Modeling
type: spec
status: active
created: 2026-06-30
---

# AEEvent Export Modeling

**Goal:** Decide and implement how area-effect event components attached to characters should be exported.

## Problem

`Character.MyAEEvent` is a runtime component reference assigned from `GetComponent<AEEvent>()`. Exporting that field directly would only record a component pointer. The meaningful data lives on the `AEEvent` component itself, and several fight scripts mutate AEEvent fields at runtime.

A correct export needs an `AEEvent` model, not a scalar `Character.MyAEEvent` column.

## Desired model

Export `AEEvent` components as first-class records linked to their host character or host GameObject.

A likely raw/clean shape:

```text
character_ae_events
- character_stable_key
- scene_or_prefab_source
- tick_damage
- tick_time
- resist_modifier
- trigger_only
- lifetap_flag
- other serialized AEEvent fields after source inspection
```

Runtime mutations by fight scripts should be treated separately: either captured through event-specific exports or documented as runtime behavior outside the static export.

## Acceptance

- `Character.MyAEEvent` remains ignored as a component reference.
- Serialized `AEEvent` component data is exported if it is useful for wiki/sheets/guide consumers.
- Runtime script mutations are not flattened into static component data unless the event script is explicitly modeled.
- Character pages or downstream consumers can distinguish characters with serialized area-effect mechanics.
