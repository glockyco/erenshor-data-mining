using HarmonyLib;

namespace JusticeForF7.Patches;

/// <summary>
/// Re-hides NPC health bars after NPC.HandleNameTag may reactivate them while
/// the main UI remains hidden.
/// </summary>
[HarmonyPatch(typeof(NPC), "HandleNameTag")]
internal static class NpcNamePlatePatch
{
    /// <summary>Injected by the runtime before patching.</summary>
    public static WorldUIHider? Hider { get; set; }

    [HarmonyPostfix]
    public static void Postfix(NamePlate? ___NamePlateObject)
    {
        Hider?.EnforceHealthBarHidden(___NamePlateObject);
    }
}
