using AdventureGuide.UI;
using HarmonyLib;
using UnityEngine.EventSystems;

namespace AdventureGuide.Patches;

/// <summary>
/// Makes EventSystem.IsPointerOverGameObject() return true when the
/// mouse is over the Adventure Guide window. The game checks this
/// method before processing mouse input for camera rotation,
/// click-to-move, and target selection.
/// </summary>
[HarmonyPatch(typeof(EventSystem), nameof(EventSystem.IsPointerOverGameObject), new System.Type[0])]
internal static class PointerOverUIPatch
{
    internal static GuideWindow? Window;

    private static void Postfix(ref bool __result)
    {
        if (!__result && Window is { Visible: true, IsMouseOver: true })
            __result = true;
    }
}
