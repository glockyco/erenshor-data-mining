using AdventureGuide.Navigation;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>Includes night despawns and encounter resets that do not call DoDeath.</summary>
[HarmonyPatch(typeof(SpawnPoint), nameof(SpawnPoint.ResetSpawnPoint))]
internal static class SpawnResetPatch
{
    internal static WorldMarkerSystem? Markers;

    [HarmonyPostfix]
    private static void Postfix() => Markers?.OnSpawnPointReset();
}
