using HarmonyLib;
using UnityEngine.EventSystems;

namespace AdventureGuide.Patches;

/// <summary>
/// Makes EventSystem.IsPointerOverGameObject() return true when Adventure
/// Guide's ImGui renderer is consuming mouse input. This covers hover, drag,
/// resize grip, scrolling, and other interactions where the game should not
/// process camera rotation, click-to-move, or target selection.
/// </summary>
[HarmonyPatch(typeof(EventSystem), nameof(EventSystem.IsPointerOverGameObject), new System.Type[0])]
internal static class PointerOverUIPatch
{
    internal static Func<bool>? WantsMouse;

    private static void Postfix(ref bool __result)
    {
        if (!__result && WantsMouse?.Invoke() == true)
            __result = true;
    }
}
