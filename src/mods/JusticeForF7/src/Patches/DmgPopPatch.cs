using HarmonyLib;
using UnityEngine;

namespace JusticeForF7.Patches;

/// <summary>
/// Harmony Prefix patches on Misc.GenPopup() and Misc.GenPopupString() to
/// suppress damage number creation while the UI is hidden.
/// </summary>
internal static class DmgPopPatch
{
    /// <summary>Injected by Plugin before patching.</summary>
    public static WorldUIHider? Hider { get; set; }

    [HarmonyPatch(typeof(Misc), nameof(Misc.GenPopup))]
    [HarmonyPrefix]
    public static bool GenPopupPrefix(int _dmg, bool _crit, GameData.DamageType _type, Transform _tar)
    {
        // Return false to skip the original method
        return Hider == null || !Hider.SuppressDamageNumbers;
    }

    [HarmonyPatch(typeof(Misc), nameof(Misc.GenPopupString))]
    [HarmonyPrefix]
    public static bool GenPopupStringPrefix(string _msg, Transform _tar)
    {
        return Hider == null || !Hider.SuppressDamageNumbers;
    }
}
