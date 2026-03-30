---
name: in-game-performance-profiling
description: Measure live runtime costs inside the running game. Use when timing HotRepl snippets, cache invalidation paths, marker/nav/tracker updates, or comparing cold vs hot behavior.
---

# In-Game Performance Profiling

Use HotRepl to time the real runtime path in the running game, not an isolated
microbenchmark. The job is to measure one named invalidation path with caches in
a known state.

Read `runtime-eval` first for the basic HotRepl workflow. This skill only covers
profiling patterns.

## What to measure

Prefer narrow paths with clear names:
- `QuestResolutionService.ResolveQuest(...)`
- `ApplyChangeSet(...)` for inventory / quest / live-source deltas
- `MarkerComputer.Recompute()` after a targeted invalidation
- `NavigationEngine.Update(playerPos)` with and without forced re-resolve
- full end-to-end path only when that is the actual question

Say explicitly whether the path is:
- cold
- hot
- single-delta incremental
- scene rebuild / hard reset

## Measurement rules

1. Look up live objects once, outside the timed loop.
2. Warm caches before measuring a hot path.
3. Force invalidation explicitly before measuring a cold or delta path.
4. Keep string building and formatting outside the timed body.
5. Report `avg / min / max`, not one run.
6. Use enough iterations to smooth noise, but keep the scenario realistic.
7. Trigger the real adapter when possible (`LiveStateTracker`, tracker events,
   inventory refresh), not only the final consumer.

## Stable Stopwatch pattern

Prefer a lambda helper over a local function. Mono's evaluator is more stable
with lambdas in larger snippets.

```bash
uv run erenshor eval run --timeout 30000 '
var sw = new System.Diagnostics.Stopwatch();
System.Func<string, int, System.Action, string> measure = (name, iterations, action) => {
    long min = long.MaxValue, max = 0, total = 0;
    for (int i = 0; i < iterations; i++) {
        sw.Restart();
        action();
        sw.Stop();
        var t = sw.ElapsedTicks;
        if (t < min) min = t;
        if (t > max) max = t;
        total += t;
    }
    double scale = 1000.0 / System.Diagnostics.Stopwatch.Frequency;
    return name + ": avg=" + (total * scale / iterations).ToString("F3")
        + " ms min=" + (min * scale).ToString("F3")
        + " ms max=" + (max * scale).ToString("F3") + " ms";
};
measure("example", 20, () => { var x = 1 + 1; })
'
```

## AdventureGuide setup pattern

When no DebugAPI helper exists yet, reflect into the live plugin once.

```bash
uv run erenshor eval run --timeout 30000 '
var plugin = UnityEngine.Resources.FindObjectsOfTypeAll<AdventureGuide.Plugin>().First();
var bf = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
var resolution = (AdventureGuide.Resolution.QuestResolutionService)plugin.GetType()
    .GetField("_resolutionService", bf).GetValue(plugin);
var marker = (AdventureGuide.Markers.MarkerComputer)plugin.GetType()
    .GetField("_markerComputer", bf).GetValue(plugin);
var nav = (AdventureGuide.Navigation.NavigationEngine)plugin.GetType()
    .GetField("_navEngine", bf).GetValue(plugin);
"ready"
'
```

## Example: live-source invalidation

This is the important gameplay-sensitive pattern: trigger a real delta, then
measure the maintained-view update.

```bash
uv run erenshor eval run --timeout 30000 '
var plugin = UnityEngine.Resources.FindObjectsOfTypeAll<AdventureGuide.Plugin>().First();
var bf = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
var live = (AdventureGuide.Markers.LiveStateTracker)plugin.GetType()
    .GetField("_liveState", bf).GetValue(plugin);
var marker = (AdventureGuide.Markers.MarkerComputer)plugin.GetType()
    .GetField("_markerComputer", bf).GetValue(plugin);
var mining = UnityEngine.Object.FindObjectsOfType<MiningNode>().FirstOrDefault();
var sw = new System.Diagnostics.Stopwatch();
System.Func<string, int, System.Action, string> measure = (name, iterations, action) => {
    long min = long.MaxValue, max = 0, total = 0;
    for (int i = 0; i < iterations; i++) {
        sw.Restart();
        action();
        sw.Stop();
        var t = sw.ElapsedTicks;
        if (t < min) min = t;
        if (t > max) max = t;
        total += t;
    }
    double scale = 1000.0 / System.Diagnostics.Stopwatch.Frequency;
    return name + ": avg=" + (total * scale / iterations).ToString("F3")
        + " ms min=" + (min * scale).ToString("F3")
        + " ms max=" + (max * scale).ToString("F3") + " ms";
};
measure("marker live delta", 10, () => {
    var cs = mining != null ? live.OnMiningChanged(mining) : AdventureGuide.State.GuideChangeSet.None;
    marker.ApplyGuideChangeSet(cs);
    marker.Recompute();
})
'
```

## Common pitfalls

- Cold vs hot ambiguity. Always state cache state.
- Measuring setup. Reflection and object lookup belong outside the loop.
- Evaluator quirks. Prefer lambdas and straight-line code over local functions.
- Timeout too low. Use `--timeout 30000` or higher for multi-iteration runs.
- Mixing semantic and rendering costs. `MarkerComputer.Recompute()` is not the
  same thing as `MarkerSystem.Update()`.
- Measuring synthetic paths only. If the gameplay problem is mining or death,
  trigger the real mining or death adapter.
