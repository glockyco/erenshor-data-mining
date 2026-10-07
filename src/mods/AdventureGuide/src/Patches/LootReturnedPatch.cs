using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>The loot window writes remaining items back when it closes.</summary>
[HarmonyPatch(typeof(LootTable), nameof(LootTable.ReturnLoot))]
internal static class LootReturnedPatch
{
    [HarmonyPostfix]
    private static void Postfix() => SpawnPatch.Loot?.MarkDirty();
}
