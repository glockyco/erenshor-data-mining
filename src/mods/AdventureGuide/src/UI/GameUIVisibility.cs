using UnityEngine;

namespace AdventureGuide.UI;

/// <summary>
/// Tracks the game's HUD Canvas visibility state.
///
/// The game hides all UI via F7 by disabling the Canvas on the TypeText
/// component (a DontDestroyOnLoad "UI" GameObject). When the game HUD is
/// hidden, the mod should hide all its visuals too — ImGui window, arrow
/// overlay, ground path, and world markers.
///
/// The Canvas reference is found once via FindObjectOfType and cached.
/// Since TypeText lives on a DontDestroyOnLoad object, the reference
/// stays valid across scene changes.
/// </summary>
internal static class GameUIVisibility
{
    private static Canvas? _hudCanvas;
    private static bool _searched;

    /// <summary>
    /// True when the game's HUD Canvas is enabled (visible).
    /// Defaults to true when the Canvas cannot be found — avoids
    /// permanently hiding the mod if the game changes its UI structure.
    /// </summary>
    public static bool IsVisible
    {
        get
        {
            if (_hudCanvas == null)
            {
                if (_searched)
                    return true;
                _searched = true;
                var typeText = UnityEngine.Object.FindObjectOfType<TypeText>();
                if (typeText != null)
                    _hudCanvas = typeText.GetComponent<Canvas>();
            }

            return _hudCanvas == null || _hudCanvas.enabled;
        }
    }
}
