using HarmonyLib;
using Sprint.Config;
using UnityEngine;

namespace Sprint.Core;

/// <summary>
/// Loader-neutral sprint lifecycle. Adapters provide settings and key state,
/// while this class owns Harmony, player discovery, input state, speed updates,
/// and cleanup shared by both loaders.
/// </summary>
internal static class SprintRuntime
{
    private const float DefaultMultiplier = 1.5f;

    private static Harmony? _harmony;
    private static ISprintSettings? _settings;
    private static Stats? _playerStats;
    private static SprintInputState _inputState;
    private static float _multiplier = DefaultMultiplier;
    private static bool _started;

    /// <summary>
    /// Starts the shared lifecycle once. A repeated start is ignored and returns
    /// false so a loader cannot install duplicate Harmony patches.
    /// </summary>
    internal static bool Start(ISprintSettings settings)
    {
        if (_started)
            return false;

        if (settings == null)
            throw new ArgumentNullException(nameof(settings));

        _settings = settings;
        _multiplier = settings.Multiplier;
        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();
        _started = true;
        return true;
    }

    /// <summary>Advances sprint state by one Unity frame.</summary>
    internal static void Tick(bool keyPressed)
    {
        if (!_started || _settings == null)
            return;

        if (_playerStats == null)
        {
            var player = GameObject.Find("Player");
            if (player != null)
                _playerStats = player.GetComponent<Stats>();
            _inputState = SprintInputPolicy.Deactivate(_inputState);
            return;
        }

        _multiplier = _settings.Multiplier;
        _inputState = SprintInputPolicy.Advance(
            _inputState,
            _settings.Enabled,
            _settings.ToggleMode,
            keyPressed
        );

        Apply(_playerStats, _inputState.Active);
    }

    /// <summary>
    /// Reapplies the game's base speed after a vanilla stat recalculation.
    /// </summary>
    internal static void OnStatsCalculated(Stats stats)
    {
        if (stats == null || !SprintEligibility.IsPlayer(_playerStats, stats))
            return;

        Apply(stats, _inputState.Active);
    }

    /// <summary>
    /// Returns whether sprint should apply to this instance.
    /// </summary>
    internal static bool IsActiveFor(Stats stats) =>
        SprintEligibility.IsActiveFor(_started, _inputState.Active, _playerStats, stats);

    /// <summary>
    /// Restores the game's unmodified speed and removes all shared state. Safe
    /// to call repeatedly during loader unload or hot reload.
    /// </summary>
    internal static void Stop()
    {
        if (!_started)
            return;

        if (_playerStats != null)
            Apply(_playerStats, false);

        _harmony?.UnpatchSelf();
        _harmony = null;
        Reset();
    }

    /// <summary>Clears static state after speed restoration and unpatching.</summary>
    internal static void Reset()
    {
        _settings = null;
        _playerStats = null;
        _inputState = default;
        _multiplier = DefaultMultiplier;
        _started = false;
    }

    /// <summary>
    /// Recomputes actualRunSpeed from base and status-effect speed, applying the
    /// configured multiplier only while sprinting.
    /// </summary>
    internal static void Apply(Stats stats, bool shouldSprint)
    {
        if (stats == null)
            return;

        float seRunSpeed = Traverse.Create(stats).Field("seRunSpeed").GetValue<float>();
        stats.actualRunSpeed = SprintEffectPolicy.CalculateActualRunSpeed(
            stats.RunSpeed,
            seRunSpeed,
            shouldSprint,
            _multiplier
        );
    }
}
