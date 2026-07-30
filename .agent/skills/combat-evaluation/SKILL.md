---
name: combat-evaluation
description: Validate Erenshor combat mechanics with shipped-code analysis and controlled HotRepl experiments. Use when checking damage or healing formulas, resistance and mitigation, resource costs, spell or skill eligibility, procs, criticals, cooldowns, repeated effects, activation rates, or combat claims for documentation. Not for runtime performance profiling.
---

# Combat Evaluation

Validate combat claims with the narrowest evidence that proves them. Read the
`runtime-eval` skill before using HotRepl. Read `in-game-performance-profiling`
only when the question is runtime cost rather than gameplay behavior.

## Evidence model

Use two complementary layers:

1. Inspect the shipped implementation and live asset metadata for exact
   branches, constants, formulas, flags, and class or level requirements.
2. Run controlled HotRepl experiments for end-to-end behavior such as displayed
   hits, resistance, healing, mana use, proc interactions, and combat messages.

Do not substitute repeated gameplay trials for a deterministic code fact. Do
not treat source inspection alone as proof that the complete runtime path
behaves as expected when a controlled cast can test it safely.

For each claim, record:

- the claim in observable terms
- the source method, branch, or asset field
- the variables held constant
- the runtime action and observation
- whether the claim was confirmed, contradicted, or only partially covered

## Workflow

### 1. Define the claim boundary

Separate compound statements before testing them. A single spell may involve:

- eligibility to enter a mechanic
- activation chance
- base damage or healing
- proficiency and stat scaling
- critical or proc modifiers
- resistance and mitigation
- resource consumption
- cooldown behavior
- displayed combat results

Test these as separate claims so a downstream modifier does not obscure an
upstream formula.

### 2. Inspect the implementation first

Locate the exact shipped method and relevant asset fields. Use source inspection
to establish control points and expected outcomes before changing live state.

Typical sources include:

- `CastSpell` for cast setup, targeting, mana use, and proc entry points
- `SpellVessel` for spell-type branches, formulas, repeated effects, and procs
- `Character` and `Stats` for resistance, mitigation, healing, resources, and
  cooldown decrement
- `UseSkill`, skill assets, spell assets, and ascension assets for eligibility,
  requirements, flags, ranks, and percentages

Check that the running game and inspected variant match. The project default is
`main`. A stale exported project can explain a source/runtime disagreement.

### 3. Snapshot live state

Capture every value and asset property that the experiment may modify. Include:

- player base and current stats
- HP, mana, stamina, and regeneration flags
- known skills and ascensions added for the experiment
- combat stance and cooldown fields
- target HP and resistances
- autoattack state
- spell or skill asset fields changed temporarily
- player and target positions when movement is required

Save originals in the REPL before mutation. Restore them before `eval reset`,
because reset discards the saved references and values.

### 4. Isolate the action

Apply only the controls required by the claim:

- Disable combat autoattack with `GameData.PlayerControl.MyCombat.ForceAttackOff()`.
- Temporarily set the test spell's `AutomateAttack` to `false`.
- Set `StopAllRegen = true` for exact HP or mana deltas.
- Set the mechanic cooldown to ready when testing activation.
- Change a base stat, then call `CalcStats()`. Derived values such as
  `CurrentRes` may be recalculated on the next frame.
- Set target resistances to known values when resistance is not the variable.
- Remove unrelated status effects, procs, equipment effects, and nearby targets
  only when they would contaminate the observation.

A target resistance of zero controls the resistance input, but the displayed
hit may still include level-based or stance-based target adjustments. Treat the
combat-log value as an end-to-end result, not automatically as pre-mitigation
damage.

### 5. Choose the proof method

#### Deterministic branches and boundaries

Exercise both sides when practical:

- eligible and ineligible spell types
- cooldown ready and cooldown active
- resistance success and guaranteed resistance
- enough mana and insufficient mana
- zero targets and one or more targets
- feature rank zero and nonzero ranks

Use exact boundary values such as 0, threshold minus 1, threshold, and threshold
plus 1.

#### Formula checks

Calculate the expected intermediate values from live inputs. Compare the narrow
formula result separately from the displayed target result.

When the formula lives in a private runtime helper, use a disposable game object
and reflection rather than inferring the formula from a mitigated hit:

```csharp
var vessel = UnityEngine.Object
    .Instantiate(GameData.EffectDB.ParticleFXVessel)
    .GetComponent<SpellVessel>();
vessel.CreateSpellChargeEffect(
    spell,
    player.transform,
    target.MyStats,
    player.MySpells,
    9999f,
    false,
    false);
var method = typeof(SpellVessel).GetMethod(
    "CalcDmgBonus",
    System.Reflection.BindingFlags.NonPublic
        | System.Reflection.BindingFlags.Instance);
var value = (int)method.Invoke(vessel, new object[] { baseDamage });
UnityEngine.Object.Destroy(vessel.gameObject);
```

Use the helper that owns the claim. Do not generalize `CalcDmgBonus` to healing,
melee, or mitigation paths that use different methods.

Three traps make a correct formula look wrong:

- **Caps applied after the term under test.** A crit multiplier applied before a
  `TargetDamage * 15` clamp is invisible when the base already exceeds the cap;
  both crit and non-crit collapse to the cap. Use a large-`TargetDamage` spell so
  `base * maxMultiplier` stays under the cap.
- **A stat that feeds both the condition and the base.** `IntScaleMod` drives the
  crit chance and `CalcDmgBonus`. When you vary it across runs, recompute the
  non-critical baseline per configuration; never reuse a baseline captured under
  different stats.
- **Displayed versus applied results.** A multiplier applied to the returned
  damage *after* `MagicDamageMe` (the SimPlayer spell crit, `num3 *= 1.2..1.6`)
  inflates the combat-log number and lifetap healing but not the HP already
  removed. Measure `target.DmgFromPlayerSource` (applied) separately from the
  logged value (displayed) to tell them apart. A player spell crit, by contrast,
  multiplies `dmgBonus` before `MagicDamageMe`, so it changes real HP.

#### Resource checks

Disable regeneration, set a known starting value, perform one action, and
compare the exact delta. Check original cost and follow-up effects separately.
Account for caps by temporarily providing enough maximum HP or mana to observe
the full result.

#### Probabilistic checks

Confirm the roll expression and bounds in source first. Then sample the narrow
runtime helper or activation path enough times to detect wiring errors.

- Use at least 1,000 iterations for ordinary percentage checks, but respect the
  scene-safety limits below: split large samples across several `eval` calls
  rather than one giant loop.
- Test every rank or threshold branch.
- Report counts and observed rates, not only percentages.
- Keep setup and object lookup outside the sample loop.
- Do not call the RNG alone. Exercise the mechanic that consumes the roll.
- Use a deterministic boundary test for 0% and 100% when available.
- Prefer a numeric discriminator over the combat log. `chatLogLines` is capped
  at 1500 and trims from the front, so counting matches across the whole log or
  a `[countBefore, countAfter)` window silently breaks once saturated (the
  window goes empty, counts can go negative). Reading a fixed tail also
  misfires: a prior iteration's line lingers when a low-output action adds few
  lines. Measure `target.DmgFromPlayerSource` deltas instead: the constant
  minimum is the non-critical baseline, larger values are crits.

A sample supports the implementation wiring. The source expression remains the
proof of the exact intended probability.

#### Mass sampling without freezing the game

Full resolution paths are expensive and side-effectful. Sampling them naively
freezes the editor and makes every subsequent `eval` (even `ping`) time out.

- `SpellVessel.ResolveSpell` instantiates a resolve-effect particle system per
  call with `cullingMode = AlwaysSimulate`. Thousands accumulate, each keeps
  simulating off-screen, and the scene grinds to a halt with no self-recovery in
  a usable timeframe. Suppress the FX by placing the target beyond the effect's
  spawn radius (40 m for spell resolves): save the target position, offset it
  (e.g. `+100` on one axis), sample, then restore. Damage still applies; only
  the cosmetic instantiation is skipped. With suppression, hundreds of resolves
  run in seconds.
- Prefer deterministic helpers with no loop for formula and magnitude claims.
  `CheckResistAmount`, `CalcDmgBonus`, and reading `resistModifier` after
  `CreateSpellProc` are instant and spawn nothing. Reserve looped full-resolves
  for probabilistic wiring only.
- Cap iterations per `eval` call (a few hundred) and split large samples across
  calls. Watch `eval ping` latency between batches: rising latency means the
  scene is bogging, so stop and let transient objects expire.
- Destroy each disposable vessel, but note the resolve FX is a separate,
  unowned object. Distance suppression is the only clean way to avoid it.
- Use pure-damage spells (`StatusEffectToApply == null`, not `Lifetap` or
  `JoltSpell`) for single-hit damage measurement. Status and DoT spells add
  asynchronous `DmgFromPlayerSource` through `TickEffects`, producing a
  continuous spread that masks the effect under test.

#### Timing and cooldown checks

Distinguish game-time units, frames, and wall-clock time. Follow the timer from
assignment through its update expression and resolution condition.

HotRepl and terminal focus can background-throttle the game. Do not validate a
60 FPS timing claim with wall-clock measurements taken while the terminal is in
focus. Derive deterministic timing from `Time.deltaTime` update code. Use the
`in-game-performance-profiling` skill only for actual runtime-cost measurements.

### 6. Capture observations

Useful live surfaces include:

- `UpdateSocialLog.chatLogLines` for hit, heal, resist, proc, and resource
  messages. Filter by `MyLogType` and message content.
- `target.DmgFromPlayerSource` for damage the training dummy received from the
  player.
- player or target HP and mana for exact resource deltas.
- mechanic-specific cooldown and status fields.

`Character.TotalDmg` measures damage dealt by that character. It is not the
training dummy's damage-received counter.

Combat-log lists may trim while the game runs. Prefer filtering recent messages
by type and unique spell or skill name over storing a list index for a long
experiment.

### 7. Reconcile all evidence

For every claim, distinguish:

- source-confirmed
- runtime-confirmed
- statistically sampled
- inferred from related behavior
- not tested

Investigate disagreements before editing documentation. Check variant mismatch,
stale exported source, target-side modifiers, asset duplication, caps, passive
skills, equipment procs, and state recalculation.

Update the documented claim only after the disagreement is explained. Preserve
implementation details only when they clarify player-visible behavior.

### 8. Restore and verify

Restore all changed state in reverse order:

- injected skills and ascensions
- spell and skill asset properties
- base stats followed by `CalcStats()`
- current resources and regeneration
- target resistances and HP
- position and target selection
- cooldowns and combat state

Remove only entries added by the experiment. Never clear a collection unless its
original state was captured and known to be empty.

Print a final state summary containing the important restored values. Then run:

```bash
uv run erenshor eval reset
```

If the evaluator becomes corrupted by an `InteractiveHost` type-emission error,
restore through existing variables before resetting. Avoid anonymous types and
callbacks or closures that capture REPL variables across evaluations.

## Reporting format

Lead with the conclusion, then provide evidence per claim:

```text
Claim: <observable statement>
Source: <method, branch, or asset field>
Control: <fixed values and disabled systems>
Runtime: <action and exact observation>
Result: confirmed | contradicted | partial
```

End with the restored-state summary and list any claims that remain source-only
or untested. Never present a source-only claim as live-confirmed.
