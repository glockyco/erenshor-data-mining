using System.Reflection;
using HarmonyLib;

namespace AdventureGuide.Patches;

/// <summary>Observes item grants even when the inventory window is closed.</summary>
[HarmonyPatch]
internal static class InventoryGrantPatch
{
    [HarmonyTargetMethods]
    private static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Method(
            typeof(Inventory),
            nameof(Inventory.AddItemToInv),
            new[] { typeof(Item) }
        );
        yield return AccessTools.Method(
            typeof(Inventory),
            nameof(Inventory.AddItemToInv),
            new[] { typeof(Item), typeof(int) }
        );
        yield return AccessTools.Method(
            typeof(Inventory),
            nameof(Inventory.ForceItemToInv),
            new[] { typeof(Item) }
        );
        yield return AccessTools.Method(
            typeof(Inventory),
            nameof(Inventory.ForceItemToInv),
            new[] { typeof(Item), typeof(int) }
        );
    }

    [HarmonyPostfix]
    private static void Postfix(Inventory __instance)
    {
        if (__instance == GameData.PlayerInv)
            InventoryPatch.NotifyChanged();
    }
}
