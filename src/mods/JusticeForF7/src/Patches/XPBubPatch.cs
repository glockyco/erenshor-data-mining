using HarmonyLib;
using UnityEngine;

namespace JusticeForF7.Patches;

/// <summary>
/// Harmony Prefix on Misc.GetXPBalls() to suppress XP orb creation
/// while the UI is hidden.
/// </summary>
[HarmonyPatch(typeof(Misc), nameof(Misc.GetXPBalls))]
internal static class XPBubPatch
{
    /// <summary>Injected by Plugin before patching.</summary>
    public static WorldUIHider? Hider { get; set; }

    [HarmonyPrefix]
    public static bool Prefix(int amt, Vector3 callPos, Transform _tar)
    {
        // Return false to skip the original method
        return Hider == null || !Hider.SuppressXPOrbs;
    }
}
