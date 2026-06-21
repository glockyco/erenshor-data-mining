using HarmonyLib;
using Lunaris;
using Sprint.Config;
using Sprint.Core;
using UnityEngine;

// See .agent/skills/mod-development/SKILL.md for mod architecture patterns

namespace Sprint;

/// <summary>
/// Native Lunaris entry point for the Sprint mod. Registers config, applies the
/// CalcStats patch, and drives per-frame sprint input.
/// </summary>
[LunarisPlugin("Sprint", PluginInfo.Version, "WoW_Much", "Configurable sprinting for Erenshor.")]
[LunarisPermission(
    LunarisPermission.Harmony | LunarisPermission.Reflection | LunarisPermission.LunarisPlugin
)]
public sealed class Plugin : LunarisPlugin
{
    private SprintSettings _settings = null!;
    private Harmony? _harmony;

    private bool _sprintActive;
    private bool _previousKeyHeld;
    private Stats? _playerStats;

    private void Awake()
    {
        _settings = Config.Register<SprintSettings>().Get();
        SprintRuntime.Multiplier = _settings.SprintMultiplier;

        _harmony = new Harmony(PluginInfo.GUID);
        _harmony.PatchAll();

        Logging.LogInfo(
            $"{PluginInfo.Name} v{PluginInfo.Version} loaded\n"
                + $"  Sprint Key: {_settings.SprintKey.DisplayString}\n"
                + $"  Toggle Mode: {(_settings.ToggleMode ? "Enabled" : "Disabled")}\n"
                + $"  Speed Multiplier: {_settings.SprintMultiplier}x"
        );
    }

    private void Update()
    {
        // Cache the player's Stats once it spawns; re-find after a scene change
        // destroys it (Unity-null check).
        if (_playerStats == null)
        {
            var player = GameObject.Find("Player");
            if (player != null)
                _playerStats = player.GetComponent<Stats>();
            SprintRuntime.PlayerStats = _playerStats;
            return;
        }

        bool keyHeld = _settings.SprintKey.IsHeld;
        if (_settings.ToggleMode)
        {
            if (keyHeld && !_previousKeyHeld)
                _sprintActive = !_sprintActive;
            _previousKeyHeld = keyHeld;
        }
        else
        {
            _sprintActive = keyHeld;
        }

        SprintRuntime.Active = _sprintActive;
        SprintRuntime.Multiplier = _settings.SprintMultiplier;
        SprintRuntime.Apply(_playerStats, _sprintActive);
    }

    private void OnDestroy()
    {
        _harmony?.UnpatchSelf();
        // Restore normal speed before clearing state so a hot reload mid-sprint
        // does not leave the player boosted until the next CalcStats call.
        if (_playerStats != null)
            SprintRuntime.Apply(_playerStats, false);
        SprintRuntime.Reset();
    }
}
