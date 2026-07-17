using HarmonyLib;

namespace JusticeForF7.Patches;

/// <summary>
/// Re-hides the target indicator after NamePlate.Update may reactivate it
/// while the main UI remains hidden.
/// </summary>
[HarmonyPatch(typeof(NamePlate), "Update")]
internal static class NamePlatePatch
{
    /// <summary>Injected by the runtime before patching.</summary>
    public static WorldUIHider? Hider { get; set; }

    [HarmonyPostfix]
    public static void Postfix(NamePlate __instance)
    {
        Hider?.EnforceTargetIndicatorHidden(__instance);
    }
}
