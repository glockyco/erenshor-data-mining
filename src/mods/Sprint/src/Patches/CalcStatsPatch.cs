using HarmonyLib;
using Sprint.Config;
using Sprint.Core;

namespace Sprint.Patches;

/// <summary>
/// Harmony patch for Stats.CalcStats to apply sprint speed multiplier.
/// Runs as a postfix to ensure it applies after all vanilla calculations.
/// </summary>
[HarmonyPatch(typeof(Stats), nameof(Stats.CalcStats))]
internal static class CalcStatsPatch
{
    private static SprintConfig? _config;

    /// <summary>
    /// Initializes the patch with configuration.
    /// Must be called before applying Harmony patches.
    /// </summary>
    public static void Initialize(SprintConfig config)
    {
        _config = config;
    }

    [HarmonyPostfix]
    private static void CalcStats_Postfix(Stats __instance)
    {
        if (_config == null)
            return;

        // Check if sprint is active for this Stats instance
        bool shouldSprint = SprintManager.IsSprintActive(__instance);

        // Apply sprint using the shared logic
        // This ensures sprint is reapplied after CalcStats recalculates stats
        // (e.g., when equipment changes, buffs expire, etc.)
        SprintManager.ApplySprint(__instance, shouldSprint);

        if (shouldSprint && _config.ModLogLevel.Value == Config.LogLevel.Debug)
        {
            Plugin.Log?.LogDebug($"Sprint reapplied in CalcStats: actualRunSpeed={__instance.actualRunSpeed:F2}");
        }
    }
}
