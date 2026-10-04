using HarmonyLib;
using UnityEngine;

namespace JusticeForF7.Patches;

/// <summary>
/// Harmony Prefix patches on Misc.GenPopup() and Misc.GenPopupString() to
/// suppress damage number creation while the UI is hidden. The class-level
/// attribute is required: Harmony.PatchAll skips classes without one.
/// </summary>
[HarmonyPatch(typeof(Misc))]
internal static class DmgPopPatch
{
    /// <summary>Injected by Plugin before patching.</summary>
    public static WorldUIHider? Hider { get; set; }

    [HarmonyPatch(nameof(Misc.GenPopup))]
    [HarmonyPrefix]
    public static bool GenPopupPrefix(
        int _dmg,
        bool _crit,
        GameData.DamageType _type,
        Transform _tar
    )
    {
        // Return false to skip the original method
        return Hider == null || !Hider.SuppressDamageNumbers;
    }

    [HarmonyPatch(nameof(Misc.GenPopupString))]
    [HarmonyPrefix]
    public static bool GenPopupStringPrefix(string _msg, Transform _tar)
    {
        return Hider == null || !Hider.SuppressDamageNumbers;
    }
}
