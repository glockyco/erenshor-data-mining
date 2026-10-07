using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>ZoneAnnounce.Start restores corpses after sceneLoaded has fired.</summary>
[HarmonyPatch(typeof(CorpseDataManager), nameof(CorpseDataManager.SpawnAllCorpses))]
internal static class CorpseSpawnPatch
{
    [HarmonyPostfix]
    private static void Postfix() => SpawnPatch.Loot?.OnSceneLoaded();
}
