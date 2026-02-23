using System.Reflection;
using System.Reflection.Emit;
using HarmonyLib;
using UnityEngine;

namespace InteractiveMapCompanion.Patches;

/// <summary>
/// Replacement for the InputManager.Map = KeyCode.None suppression hack in
/// MapOverlay. When the mod intercepts the map key, MapOverlay.Update() sets
/// SuppressMapKey = true. Two patches here prevent the game from also reacting
/// to that same keypress:
///
///   1. A Prefix on HotkeyManager.OpenCloseMap() skips the call entirely,
///      covering the PlayerControl.Update() → OpenCloseMap() path.
///
///   2. A Transpiler on Minimap.Update() replaces Input.GetKeyDown(InputManager.Map)
///      with a helper that additionally checks !SuppressMapKey, covering the
///      minimap small↔large zoom toggle path.
///
/// MapOverlay.LateUpdate() clears SuppressMapKey after all Update() calls for
/// the frame have completed. [DefaultExecutionOrder(-100)] on MapOverlay ensures
/// it sets the flag before Minimap and PlayerControl (both at default order 0)
/// read it, making the suppression order-safe.
/// </summary>
internal static class MapKeyPatches
{
    /// <summary>
    /// Set by MapOverlay.Update() when it intercepts the map key. Cleared by
    /// MapOverlay.LateUpdate(). Read by the two patches below.
    /// </summary>
    internal static bool SuppressMapKey;

    /// <summary>
    /// Called from the patched Minimap.Update() IL in place of
    /// Input.GetKeyDown(InputManager.Map). Returns false when the mod has
    /// already consumed the keypress this frame.
    /// </summary>
    internal static bool GetKeyDownUnlessSuppressed(KeyCode key) =>
        !SuppressMapKey && Input.GetKeyDown(key);
}

/// <summary>
/// Skips HotkeyManager.OpenCloseMap() when the map key has been consumed by
/// the mod overlay this frame. This is order-independent because Harmony
/// intercepts at call time, not during Update() scheduling.
/// </summary>
[HarmonyPatch(typeof(HotkeyManager), nameof(HotkeyManager.OpenCloseMap))]
internal static class OpenCloseMapPatch
{
    [HarmonyPrefix]
    private static bool Prefix() => !MapKeyPatches.SuppressMapKey;
}

/// <summary>
/// Transpiler on Minimap.Update() that replaces the Input.GetKeyDown call in
/// the minimap zoom toggle branch with MapKeyPatches.GetKeyDownUnlessSuppressed.
/// Only that one call site is changed; the UseMap visibility sync block at the
/// top of Update() is unaffected.
///
/// IL match: ldsfld KeyCode InputManager::Map
///           call   bool UnityEngine.Input::GetKeyDown(KeyCode)
///
/// This pair is unique in Minimap.Update() as of the current game version. If
/// a future update adds another GetKeyDown(InputManager.Map) call to the method,
/// the InvalidOperationException below will catch it during mod load.
/// </summary>
[HarmonyPatch(typeof(Minimap), "Update")]
internal static class MinimapUpdatePatch
{
    private static readonly MethodInfo _getKeyDown = typeof(Input).GetMethod(
        nameof(Input.GetKeyDown),
        [typeof(KeyCode)]
    )!;

    private static readonly FieldInfo _inputManagerMap = typeof(InputManager).GetField(
        nameof(InputManager.Map)
    )!;

    private static readonly MethodInfo _helper = typeof(MapKeyPatches).GetMethod(
        nameof(MapKeyPatches.GetKeyDownUnlessSuppressed),
        BindingFlags.NonPublic | BindingFlags.Static
    )!;

    [HarmonyTranspiler]
    private static IEnumerable<CodeInstruction> Transpiler(
        IEnumerable<CodeInstruction> instructions
    )
    {
        var codes = new List<CodeInstruction>(instructions);
        bool patched = false;

        for (int i = 0; i < codes.Count - 1; i++)
        {
            bool isMapField =
                codes[i].opcode == OpCodes.Ldsfld
                && codes[i].operand is FieldInfo f
                && f == _inputManagerMap;

            bool isGetKeyDown =
                codes[i + 1].opcode == OpCodes.Call
                && codes[i + 1].operand is MethodInfo m
                && m == _getKeyDown;

            if (isMapField && isGetKeyDown)
            {
                // Replace Input.GetKeyDown with our wrapper; keep the ldsfld.
                codes[i + 1] = new CodeInstruction(OpCodes.Call, _helper);
                patched = true;
                break;
            }
        }

        if (!patched)
            throw new InvalidOperationException(
                "[InteractiveMapCompanion] MinimapUpdatePatch: could not find "
                    + "Input.GetKeyDown(InputManager.Map) in Minimap.Update(). "
                    + "The game may have been updated — please update the transpiler."
            );

        return codes;
    }
}
