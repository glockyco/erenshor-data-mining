---
title: AEEvent Export Modeling
type: spec
status: implemented
created: 2026-06-30
archived: 2026-07-05
---

# AEEvent Export Modeling

**Goal:** Export serialized `AEEvent` and `AEEvent2` component data as first-class records linked to their host character, plus structured mutation descriptors for fight scripts that escalate AE fields at runtime.

## Problem

`Character.MyAEEvent` is a runtime cache assigned in `Awake()` via `GetComponent<AEEvent>()`, not a serialized reference. The meaningful data lives on the `AEEvent` component's own serialized fields. Several boss fight scripts mutate those fields at runtime — `tickDmg`, `TickTime`, `ResistMod` — as phase-escalation mechanics, and the mutated values are the interesting ones for boss encounters.

Two component types exist:
- `AEEvent` — full field set: `tickDmg`, `TickTime`, `TickRange`, `ResistMod`, `ResistType`, `EventHappens`, `DamageReason`, `addEffect`, `isLifetap`, `lifetapHealMod`, `TriggerOnly`, `Dust`.
- `AEEvent2` — reduced field set: `tickDmg`, `TickTime`, `EventHappens`, `DamageReason`, `Dust`. Used by different fight scripts; no resist/lifetap/trigger fields.

## Desired model

### Layer 1 — Static baseline (auto-exported)

Export `AEEvent` and `AEEvent2` component serialized fields as the starting/phase-1 values the asset scanner can read from the prefab. One record per attached component, linked to the host character stable key.

```text
character_ae_events
- character_stable_key
- component_type           (AEEvent | AEEvent2)
- tick_damage
- tick_time
- tick_range               (AEEvent only)
- resist_modifier          (AEEvent only)
- resist_type              (AEEvent only)
- event_happens
- damage_reason
- add_effect_spell_key     (AEEvent only; nullable)
- is_lifetap               (AEEvent only)
- lifetap_heal_mod         (AEEvent only)
- trigger_only             (AEEvent only)
```

### Layer 2 — Mutation descriptors (code-facts extracted)

For fight scripts that mutate AE fields, extract the constants and trigger conditions via code-facts matchers against the decompiled source. Store as structured note rows, not as computed final values. Three mutation patterns exist in the wild:

**Serialized escalation parameters** — the script's own `public` fields drive the mutation, so they are auto-extractable. Example: `DPSCheckAEEvent` (`UpdateFrequencyInSeconds`, `IncreaseDmgAmt`, `IncreaseModifierAmt`, `maxTicks`).

**Hardcoded constants** — C# statement literals in fight scripts. Extractable via code-facts pattern-matching `field.tickDmg += N` / `field.tickDmg = N` in the decompiled source. Examples:
- `BraxFightEvent`: `tickDmg += 200`, `ResistMod += 8` every 600s; reset to `baseAEDmg=1500` / `baseAEMod=150` on crystal break.
- `MizukiEvent`: on HP < 1M, `tickDmg = 9000`, `TickTime = 220`, `TriggerOnly = false`.
- `FaithTracker`: on trigger, `tickDmg += 1000`, `ResistMod += 33`.
- `SprinklesEvent`: per ward wave, `Offensive.tickDmg += wave*200`, `ResistMod += wave*7`, `Lifetap.tickDmg += wave*120`.
- `StowawayPortal`: on spawn, `tickDmg = 6500`.

**Conditional on runtime state** — the mutation depends on live HP-delta thresholds that cannot be computed at export time. Example: `InfernoTwins`/`RewardListener` uses `AEMult = 8` when HP-delta ≥ 80%, `AEMult = 2` when ≥ 60%, then `tickDmg = 6000 * AEMult`. These are documented as fight mechanics in wiki text, not as structured data.

### Layer 2 table shape

```text
ae_event_mutations
- character_stable_key          (the character whose AEEvent is mutated)
- script_type                   (BraxFightEvent, MizukiEvent, etc.)
- trigger                       (periodic | hp_threshold | on_spawn | on_event)
- trigger_condition             (e.g. "hp < 1000000", "every 600s", "ward_wave")
- tick_damage_formula           (e.g. "+200", "=9000", "=6000*AEMult")
- tick_time_formula
- resist_modifier_formula
- other_field_formulas          (JSON: {field: formula})
- documented_limitation         (nullable; for runtime-state-conditional mutations)
```

## Acceptance

- `Character.MyAEEvent` remains ignored as a runtime component cache.
- Serialized `AEEvent` and `AEEvent2` component data is exported as baseline records.
- Mutation descriptors are extracted for scripts with serialized or hardcoded constants.
- Runtime-state-conditional mutations (InfernoTwins) are documented as a limitation with the trigger logic described in `documented_limitation`.
- Character pages or downstream consumers can distinguish characters with area-effect mechanics and see their escalation curves.
