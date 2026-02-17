using BepInEx;
using BepInEx.Logging;
using HarmonyLib;
using Sprint.Config;
using Sprint.Core;
using Sprint.Patches;

namespace Sprint;

/// <summary>
/// Main plugin entry point for Sprint mod.
/// Adds configurable sprinting functionality to the game.
/// </summary>
[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
public sealed class Plugin : BaseUnityPlugin
{
    internal static ManualLogSource Log { get; private set; } = null!;

    private Harmony? _harmony;

    private void Awake()
    {
        Log = Logger;

        // Initialize configuration
        var config = new SprintConfig(Config);

        // Initialize components with configuration
        SprintManager.Initialize(config, Log);
        CalcStatsPatch.Initialize(config);

        // Add SprintManager MonoBehaviour for input handling
        gameObject.AddComponent<SprintManager>();

        // Apply Harmony patches
        _harmony = new Harmony(PluginInfo.GUID);
        try
        {
            _harmony.PatchAll();
            Log.LogInfo("Harmony patches applied successfully");

            // List what was patched
            var patchedMethods = _harmony.GetPatchedMethods();
            foreach (var method in patchedMethods)
            {
                Log.LogInfo($"  Patched: {method.DeclaringType?.Name}.{method.Name}");
            }
        }
        catch (System.Exception ex)
        {
            Log.LogError($"Failed to apply Harmony patches: {ex}");
        }

        Log.LogInfo($"{PluginInfo.Name} v{PluginInfo.Version} loaded");
        Log.LogInfo($"  Sprint Key: {config.SprintKey.Value}");
        Log.LogInfo($"  Toggle Mode: {(config.ToggleMode.Value ? "Enabled" : "Disabled")}");
        Log.LogInfo($"  Speed Multiplier: {config.SprintMultiplier.Value}x");
    }

    private void OnDestroy()
    {
        _harmony?.UnpatchSelf();
    }
}
