using BepInEx.Logging;
using HarmonyLib;
using Sprint.Config;
using UnityEngine;

namespace Sprint.Core;

/// <summary>
/// Manages sprint state and input handling.
/// Runs as a MonoBehaviour to handle per-frame input checking and speed application.
/// </summary>
public class SprintManager : MonoBehaviour
{
    private static SprintManager? _instance;
    private static SprintConfig? _config;
    private static ManualLogSource? _log;

    private bool _sprintActive;
    private bool _previousKeyState;
    private Stats? _playerStats;

    /// <summary>
    /// Initializes the SprintManager with configuration and logger.
    /// Must be called before accessing IsSprintActive.
    /// </summary>
    public static void Initialize(SprintConfig config, ManualLogSource log)
    {
        _config = config;
        _log = log;
    }

    /// <summary>
    /// Returns whether sprint is currently active for the given Stats instance.
    /// </summary>
    public static bool IsSprintActive(Stats stats)
    {
        if (_instance == null)
            return false;

        // Only apply to player
        if (_instance._playerStats == null || stats != _instance._playerStats)
            return false;

        return _instance._sprintActive;
    }

    /// <summary>
    /// Applies sprint speed modification to the given Stats instance.
    /// Recalculates from base components to ensure correctness.
    /// </summary>
    public static void ApplySprint(Stats stats, bool shouldSprint)
    {
        if (stats == null || _config == null)
            return;

        // Access private seRunSpeed field via Harmony Traverse
        float seRunSpeed = Traverse.Create(stats).Field("seRunSpeed").GetValue<float>();

        if (shouldSprint)
        {
            // Apply sprint to TOTAL speed (base + status effects)
            stats.actualRunSpeed = (stats.RunSpeed + seRunSpeed) * _config.SprintMultiplier.Value;
        }
        else
        {
            // Reset to normal speed when not sprinting
            stats.actualRunSpeed = stats.RunSpeed + seRunSpeed;
        }

        // Respect game's minimum speed cap
        if (stats.actualRunSpeed < 2f)
        {
            stats.actualRunSpeed = 2f;
        }
    }

    private void Awake()
    {
        _instance = this;
        _sprintActive = false;
        _previousKeyState = false;
    }

    private void Update()
    {
        if (_config == null)
            return;

        // Find and cache player Stats if not already found
        if (_playerStats == null)
        {
            GameObject? player = GameObject.Find("Player");
            if (player != null)
            {
                _playerStats = player.GetComponent<Stats>();
                if (_playerStats != null && _log != null)
                {
                    _log.LogDebug("Sprint: Player found and cached");
                }
            }
            return;
        }

        // Handle input
        bool keyCurrentlyPressed = Input.GetKey(_config.SprintKey.Value);

        if (_config.ToggleMode.Value)
        {
            // Toggle mode: tap to toggle sprint on/off
            if (keyCurrentlyPressed && !_previousKeyState)
            {
                _sprintActive = !_sprintActive;
                if (_log != null && _config.ModLogLevel.Value == Config.LogLevel.Debug)
                {
                    _log.LogDebug($"Sprint toggled: {(_sprintActive ? "ON" : "OFF")}");
                }
            }
            _previousKeyState = keyCurrentlyPressed;
        }
        else
        {
            // Hold mode: hold key to sprint
            if (_sprintActive != keyCurrentlyPressed && _log != null && _config.ModLogLevel.Value == Config.LogLevel.Debug)
            {
                _log.LogDebug($"Sprint: {(keyCurrentlyPressed ? "ON" : "OFF")}");
            }
            _sprintActive = keyCurrentlyPressed;
        }

        // Apply sprint speed modification every frame
        ApplySprint(_playerStats, _sprintActive);
    }

    private void OnDestroy()
    {
        if (_instance == this)
        {
            _instance = null;
        }
    }
}
