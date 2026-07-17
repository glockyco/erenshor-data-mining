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
    private static Func<bool>? _isSprintPressed;
    private static Stats? _playerStats;
    private static bool _sprintToggled;
    private static bool _previousKeyPressed;
    private static bool _active;
    private static float _multiplier = DefaultMultiplier;
    private static bool _started;

    /// <summary>
    /// Starts the shared lifecycle once. A repeated start is ignored and returns
    /// false so a loader cannot install duplicate Harmony patches.
    /// </summary>
    internal static bool Start(ISprintSettings settings, Func<bool> isSprintPressed)
    {
        if (_started)
            return false;

        if (settings == null)
            throw new ArgumentNullException(nameof(settings));
        if (isSprintPressed == null)
            throw new ArgumentNullException(nameof(isSprintPressed));

        _settings = settings;
        _isSprintPressed = isSprintPressed;
        _multiplier = settings.Multiplier;
        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();
        _started = true;
        return true;
    }

    /// <summary>
    /// Checks a configured shortcut using the supplied key reader. Keeping the
    /// predicate independent from Unity input makes loader adapters testable and
    /// avoids BepInEx's input abstraction on the native game input path.
    /// </summary>
    internal static bool IsShortcutPressed(
        KeyCode mainKey,
        IReadOnlyList<KeyCode> modifiers,
        Func<KeyCode, bool> isKeyPressed
    )
    {
        if (mainKey == KeyCode.None || !isKeyPressed(mainKey))
            return false;

        for (int i = 0; i < modifiers.Count; i++)
        {
            if (!isKeyPressed(modifiers[i]))
                return false;
        }

        return true;
    }

    /// <summary>Advances input and speed state by one Unity frame.</summary>
    internal static void Tick()
    {
        if (!_started || _settings == null || _isSprintPressed == null)
            return;

        if (_playerStats == null)
        {
            var player = GameObject.Find("Player");
            if (player != null)
                _playerStats = player.GetComponent<Stats>();
            _active = false;
            return;
        }

        bool keyPressed = _isSprintPressed();
        _multiplier = _settings.Multiplier;

        if (!_settings.Enabled)
        {
            _sprintToggled = false;
            _active = false;
            _previousKeyPressed = keyPressed;
        }
        else if (_settings.ToggleMode)
        {
            if (keyPressed && !_previousKeyPressed)
                _sprintToggled = !_sprintToggled;
            _previousKeyPressed = keyPressed;
            _active = _sprintToggled;
        }
        else
        {
            _previousKeyPressed = keyPressed;
            _active = keyPressed;
        }

        Apply(_playerStats, _active);
    }

    /// <summary>
    /// Reapplies the game's base speed after a vanilla stat recalculation.
    /// </summary>
    internal static void OnStatsCalculated(Stats stats) => Apply(stats, IsActiveFor(stats));

    /// <summary>
    /// Returns whether sprint should apply to this instance.
    /// </summary>
    internal static bool IsActiveFor(Stats stats) =>
        _started && _active && _playerStats != null && stats == _playerStats;

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
        _isSprintPressed = null;
        _playerStats = null;
        _sprintToggled = false;
        _previousKeyPressed = false;
        _active = false;
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
        stats.actualRunSpeed = shouldSprint
            ? (stats.RunSpeed + seRunSpeed) * _multiplier
            : stats.RunSpeed + seRunSpeed;

        if (stats.actualRunSpeed < 2f)
            stats.actualRunSpeed = 2f;
    }
}
