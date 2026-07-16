using HarmonyLib;
using Sprint.Core;

namespace Sprint.Patches;

/// <summary>
/// Reapplies the sprint multiplier after Stats.CalcStats recomputes speed (e.g.
/// on equipment changes or buff expiry), so vanilla recalculation never
/// overwrites sprint. Only the player's Stats are affected; see SprintRuntime.
/// </summary>
[HarmonyPatch(typeof(Stats), nameof(Stats.CalcStats))]
internal static class CalcStatsPatch
{
    [HarmonyPostfix]
    private static void CalcStats_Postfix(Stats __instance) =>
        SprintRuntime.OnStatsCalculated(__instance);
}
