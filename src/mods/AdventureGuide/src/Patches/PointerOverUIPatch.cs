using AdventureGuide.Rendering;
using HarmonyLib;
using UnityEngine.EventSystems;

namespace AdventureGuide.Patches;

/// <summary>
/// Makes EventSystem.IsPointerOverGameObject() return true when ImGui
/// is consuming mouse input. This covers hover, drag, resize grip,
/// scrolling — any interaction where the game should not process
/// camera rotation, click-to-move, or target selection.
/// </summary>
[HarmonyPatch(typeof(EventSystem), nameof(EventSystem.IsPointerOverGameObject), new System.Type[0])]
internal static class PointerOverUIPatch
{
    internal static ImGuiRenderer? Renderer;

    private static void Postfix(ref bool __result)
    {
        if (!__result && Renderer is { WantCaptureMouse: true })
            __result = true;
    }
}