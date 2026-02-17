using HarmonyLib;

namespace JusticeForF7.Patches;

/// <summary>
/// Harmony Postfix on TypeText.Update() to detect F7 Canvas state transitions.
/// Compares GameData.MainCanvas.enabled to a cached value each frame and
/// triggers hide/show on the WorldUIHider when the state changes.
/// </summary>
[HarmonyPatch(typeof(TypeText), "Update")]
internal static class TypeTextPatch
{
    /// <summary>Injected by Plugin before patching.</summary>
    public static WorldUIHider? Hider { get; set; }

    private static bool? _lastCanvasEnabled = null;

    /// <summary>
    /// Resets the cached canvas state. Called on scene load to re-sync with
    /// the new scene's canvas state, matching the game's behavior of not
    /// persisting F7 state across scenes.
    /// </summary>
    public static void ResetState()
    {
        _lastCanvasEnabled = null;
    }

    [HarmonyPostfix]
    public static void Postfix()
    {
        if (Hider == null)
            return;

        var canvas = GameData.MainCanvas;
        if (canvas == null)
            return;

        bool currentEnabled = canvas.enabled;

        // First run: initialize without triggering state change
        if (_lastCanvasEnabled == null)
        {
            _lastCanvasEnabled = currentEnabled;
            return;
        }

        if (currentEnabled == _lastCanvasEnabled.Value)
        {
            // No state change, but run periodic re-scan tick if hidden
            Hider.Tick();
            return;
        }

        _lastCanvasEnabled = currentEnabled;

        if (!currentEnabled)
            Hider.OnUIHidden();
        else
            Hider.OnUIShown();
    }
}
