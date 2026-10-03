---
name: in-game-performance-profiling
description: Use when measuring a live mod path in Erenshor, including marker updates, invalidation, and hot-versus-rebuild costs.
---

# In-game performance profiling

Start HotRepl as described in `runtime-eval`. This skill covers timing only. Measure the method that the running game calls, not an isolated replacement.

## Prepare the measurement

1. Select one path and name its cache state: hot, forced rebuild, scene rebuild, or one gameplay delta.
2. Look up game objects and private fields before starting the clock. Warm the hot path first.
3. Trigger invalidation before each forced-rebuild sample. Do not time the invalidation unless it is the target.
4. Run several samples, then report average, minimum, and maximum in milliseconds. Keep rendering, logging, and formatting outside the timed loop when they are not the target.
5. For a mining, inventory, quest, or death regression, also measure the real game event or patch path. Calling a final consumer alone omits upstream work.

## Example: AdventureGuide marker update

Enter a gameplay scene and enable world markers first. This measures `WorldMarkerSystem.Update` with a hot cache, then with `MarkSpawnDirty()` before each sample. The second series forces marker rebuilds, not a scene reload.

```bash
uv run erenshor eval run --timeout 30000 '
var plugin = UnityEngine.Resources.FindObjectsOfTypeAll<AdventureGuide.Plugin>().First();
var flags = System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance;
var runtime = plugin.GetType().GetField("_runtime", flags).GetValue(plugin);
var markers = (AdventureGuide.Navigation.WorldMarkerSystem)runtime.GetType().GetField("_markers", flags).GetValue(runtime);
if (GameData.PlayerControl == null || !markers.Enabled) throw new System.InvalidOperationException("Enter a gameplay scene and enable world markers");
var scene = SceneManager.GetActiveScene().name;
markers.Update(scene);
System.Func<bool, string> profile = force => {
    var sw = new System.Diagnostics.Stopwatch();
    long min = long.MaxValue, max = 0, total = 0;
    for (int i = 0; i < 12; i++) {
        if (force) markers.MarkSpawnDirty();
        sw.Restart();
        markers.Update(scene);
        sw.Stop();
        long ticks = sw.ElapsedTicks;
        if (ticks < min) min = ticks;
        if (ticks > max) max = ticks;
        total += ticks;
    }
    double ms = 1000.0 / System.Diagnostics.Stopwatch.Frequency;
    return (force ? "forced rebuild" : "hot") + ": avg=" + (total * ms / 12).ToString("F3")
        + " ms min=" + (min * ms).ToString("F3") + " ms max=" + (max * ms).ToString("F3") + " ms";
};
profile(false) + "\n" + profile(true)
'
```

`WorldMarkerSystem.Update` also updates live marker positions. Do not describe this number as pure quest resolution. For a real spawn or death delta, time its Harmony patch path and the next marker update separately. Increase `--timeout` for a longer run, but keep the sample count realistic. If ScriptEngine reloads during measurement, repeat the setup because HotRepl resets stored variables.
