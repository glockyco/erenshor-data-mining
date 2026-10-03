---
name: combat-evaluation
description: Validate Erenshor damage, healing, resistance, costs, procs, or cooldown claims. Use shipped combat code and controlled HotRepl experiments, not runtime-cost profiling.
---

# Combat evaluation

## Prepare

1. Read the `runtime-eval` skill before connecting to HotRepl.
2. Select the same game variant for the running game, exported scripts, and assets.
3. Inspect the shipped method and asset fields before changing live state.
   Start with `CastSpell`, `SpellVessel`, `Character`, `Stats`, or `UseSkill` as the claim requires.
4. Split the claim into eligibility, activation, formula, resistance, applied effect,
   displayed result, resource cost, and cooldown as needed.
   Record the expected branches and boundary values before the experiment.
5. Save player and target resources, stats, resistances, positions, regeneration flags,
   autoattack state, cooldowns, known skills, and modified asset fields in REPL variables.
   Change only values relevant to the claim.

## Run the experiment

1. Stop autoattack with `GameData.PlayerCombat.ForceAttackOff()`.
   Disable the test spell's `AutomateAttack` if needed.
   Set `StopAllRegen` for exact resource deltas.
   After a base-stat change, call `CalcStats()` and allow derived stats to refresh.
2. Exercise both sides of deterministic boundaries when safe.
   Calculate expected formula values from live inputs before comparing HP or log output.
   Zero target resistance does not remove level and stance modifiers.
3. For random effects, inspect the roll expression in shipped code.
   Sample the mechanic that consumes the roll, not the RNG alone.
   Report counts and observed rates.
   Split large samples into batches of a few hundred.
   Check `uv run erenshor eval ping` between batches.
4. Compare applied damage with the target's HP delta or its private
   `Character.DmgFromPlayerSource` field through reflection.
   Compare displayed damage with recent `UpdateSocialLog.chatLogLines` entries.
   Do not use `Character.TotalDmg` as damage received by the target.
5. Restore changed state in reverse order, including positions and asset fields.
   Remove only skills and effects added by the experiment.
   Confirm restored values before `uv run erenshor eval reset`, which discards REPL variables.
   Close the game after the experiment.

## Pitfalls

- `SpellVessel.ResolveSpell` and `Character.MagicDamageMe` can clamp damage
  at `spell.TargetDamage * 15`. Keep test values below the cap to measure a multiplier.
- Changing `IntScaleMod` can change both damage and critical chance.
  Recompute the noncritical baseline after each change.
- The SimPlayer critical branch multiplies the result of `MagicDamageMe` after
  HP has changed. Its combat-log number can exceed applied damage.
- `UpdateSocialLog.chatLogLines` trims from the front after 1500 entries.
  Saved log indexes and fixed tails can miscount long samples.
  Prefer HP or reflected damage deltas for repeated hits.
- `SpellVessel.ResolveSpell` creates resolve FX for a damage target within 40 m
  of the player. Each FX can keep simulating.
  For large controlled damage samples, move the target beyond 40 m and restore it afterward.
  Inspect the spell branch before relying on this suppression.
- A status or DoT spell can add asynchronous damage.
  Use a pure-damage spell when one hit must have one measured delta.
- Focus changes can throttle the game.
  Derive cooldown units from the code's update expression instead of wall-clock time.

Record each conclusion with its source method or asset field, controls, action,
observation, and confidence. Separate source-confirmed, live-confirmed, sampled,
and untested claims. Investigate disagreements before publishing a combat claim.
