using System.Reflection;
using HarmonyLib;

namespace AdventureGuide.Patches;

[HarmonyPatch]
internal static class PlayerTypingPatch
{
    internal static Func<bool>? WantsTextInput;

    private static IEnumerable<MethodBase> TargetMethods()
    {
        yield return AccessTools.Method(typeof(BankUI), "Update");
        yield return AccessTools.Method(typeof(GuildManagerUI), "Update");
        yield return AccessTools.Method(typeof(AuctionHouseUI), "Update");
    }

    private static void Postfix()
    {
        if (WantsTextInput?.Invoke() == true)
            GameData.PlayerTyping = true;
    }
}
