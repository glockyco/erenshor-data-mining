"""AEEvent mutation descriptors for boss fight scripts.

These describe how fight scripts mutate AEEvent component fields at runtime.
The data is derived from decompiled game scripts and pinned by code-facts
assert specs (see ``src/tools/CodeFacts/specs/erenshor-facts.json``). Each
assert protects a critical mutation value from drifting silently after a game
update; if the decompiled statement changes shape, the code-facts step fails.

Three mutation patterns:
  - serialized: the script's own public fields drive the mutation (DPSCheckAEEvent)
  - hardcoded: C# statement literals (BraxFightEvent, MizukiEvent, etc.)
  - runtime_conditional: depends on live HP-delta thresholds (InfernoTwins)

Runtime-conditional mutations are documented with ``documented_limitation``
rather than structured formulas, since the final values cannot be computed
without simulating the fight.
"""

from __future__ import annotations

AE_EVENT_MUTATIONS: list[dict[str, object]] = [
    {
        # code-fact: ae.brax_escalation
        # code-fact: ae.brax_reset
        "character_stable_key": "character:brax",
        "script_type": "BraxFightEvent",
        "trigger": "periodic",
        "trigger_condition": "every 600s (200s when HP < 15%)",
        "tick_damage_formula": "+200",
        "tick_time_formula": "",
        "resist_modifier_formula": "+8",
        "other_field_formulas": "{}",
        "documented_limitation": "",
    },
    {
        "character_stable_key": "character:brax",
        "script_type": "BraxFightEvent",
        "trigger": "on_event",
        "trigger_condition": "crystal break resets AE",
        "tick_damage_formula": "=1500",
        "tick_time_formula": "",
        "resist_modifier_formula": "=150",
        "other_field_formulas": "{}",
        "documented_limitation": "",
    },
    {
        # code-fact: ae.mizuki_final
        "character_stable_key": "character:mizuki",
        "script_type": "MizukiEvent",
        "trigger": "hp_threshold",
        "trigger_condition": "HP < 1000000 (final phase)",
        "tick_damage_formula": "=9000",
        "tick_time_formula": "=220",
        "resist_modifier_formula": "",
        "other_field_formulas": '{"TriggerOnly": "=false"}',
        "documented_limitation": "",
    },
    {
        # code-fact: ae.faith_escalation
        "character_stable_key": "character:faith",
        "script_type": "FaithTracker",
        "trigger": "on_event",
        "trigger_condition": "FaithTracker trigger",
        "tick_damage_formula": "+1000",
        "tick_time_formula": "",
        "resist_modifier_formula": "+33",
        "other_field_formulas": "{}",
        "documented_limitation": "",
    },
    {
        "character_stable_key": "character:sprinkles",
        "script_type": "SprinklesEvent",
        "trigger": "on_event",
        "trigger_condition": "per ward wave cleared",
        "tick_damage_formula": "+wave*200 (offensive), +wave*120 (lifetap)",
        "tick_time_formula": "",
        "resist_modifier_formula": "+wave*7",
        "other_field_formulas": "{}",
        "documented_limitation": "",
    },
    {
        "character_stable_key": "",
        "script_type": "DPSCheckAEEvent",
        "trigger": "periodic",
        "trigger_condition": "every UpdateFrequencyInSeconds (serialized), up to maxTicks times",
        "tick_damage_formula": "+IncreaseDmgAmt (serialized)",
        "tick_time_formula": "",
        "resist_modifier_formula": "+IncreaseModifierAmt (serialized)",
        "other_field_formulas": "{}",
        "documented_limitation": "Escalation parameters are serialized on the script component; "
        "see character_ae_events for baseline values.",
    },
    {
        "character_stable_key": "",
        "script_type": "StowawayPortal",
        "trigger": "on_spawn",
        "trigger_condition": "on skeleton spawn",
        "tick_damage_formula": "=6500",
        "tick_time_formula": "",
        "resist_modifier_formula": "",
        "other_field_formulas": "{}",
        "documented_limitation": "",
    },
    {
        "character_stable_key": "character:frost",
        "script_type": "InfernoTwins",
        "trigger": "hp_threshold",
        "trigger_condition": "HP-delta >= 80% -> AEMult=8; >= 60% -> AEMult=2; on twin death -> AEMult-based override",
        "tick_damage_formula": "=6000*AEMult (rage), =3000*AEMult (rage escalation)",
        "tick_time_formula": "=300/AEMult (twin death), =600/AEMult (rage escalation)",
        "resist_modifier_formula": "=65*AEMult",
        "other_field_formulas": '{"AttackAbility": "+RageLevel*400"}',
        "documented_limitation": "AEMult depends on live HP-delta between twins, which cannot be computed "
        "at export time. Values shown are the formula templates; actual runtime "
        "values vary by fight state.",
    },
    {
        "character_stable_key": "character:inferno",
        "script_type": "InfernoTwins",
        "trigger": "hp_threshold",
        "trigger_condition": "HP-delta >= 80% -> AEMult=8; >= 60% -> AEMult=2; on twin death -> AEMult-based override",
        "tick_damage_formula": "=6000*AEMult (rage), =3000*AEMult (rage escalation)",
        "tick_time_formula": "=300/AEMult (twin death), =600/AEMult (rage escalation)",
        "resist_modifier_formula": "=65*AEMult",
        "other_field_formulas": '{"AttackAbility": "+RageLevel*400"}',
        "documented_limitation": "AEMult depends on live HP-delta between twins, which cannot be computed "
        "at export time. Values shown are the formula templates; actual runtime "
        "values vary by fight state.",
    },
]
