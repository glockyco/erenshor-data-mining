using UnityEngine;

namespace AdventureGuide.UI;

/// <summary>
/// Detects when non-permanent game UI windows overlap the quest tracker.
///
/// The tracker (ImGui) renders on top of Unity's Canvas, so it obscures
/// game windows like inventory, vendor, and bank panels. This class tracks
/// which game windows are open and whether they overlap the tracker's
/// screen rect, allowing the tracker to suppress itself.
///
/// <b>Design rules:</b>
/// <list type="bullet">
///   <item>Check overlap on open-transition only (window went from inactive
///     to active this frame). Don't re-check continuously.</item>
///   <item>Cache window screen rects — positions only change in
///     <see cref="GameData.EditUIMode"/>. Invalidate on scene change or
///     when edit mode is exited.</item>
///   <item>Use <see cref="CameraController"/>'s UIWindows list — the game's
///     own curated set of non-permanent, toggleable windows.</item>
/// </list>
///
/// Coordinate convention: all rects use screen pixels with Y-down (ImGui
/// convention). Unity's WorldToScreenPoint returns Y-up, so we flip on
/// cache.
/// </summary>
internal static class GameWindowOverlap
{
    /// <summary>Cached screen rect for a game UI window (Y-down coords).</summary>
    private struct WindowRect
    {
        public float Left,
            Top,
            Right,
            Bottom;

        public bool Overlaps(float otherLeft, float otherTop, float otherRight, float otherBottom)
        {
            return Left < otherRight && Right > otherLeft && Top < otherBottom && Bottom > otherTop;
        }
    }

    private static List<GameObject>? _uiWindows;
    private static bool _searched;

    // Cached screen rects, indexed parallel to _uiWindows.
    private static WindowRect[]? _rects;

    // Previous frame's activeSelf state, indexed parallel to _uiWindows.
    // Used to detect open-transitions (was false, now true).
    private static bool[]? _wasActive;

    // Windows currently suppressing the tracker (became active while
    // overlapping). Tracked by index into _uiWindows. Cleared when
    // the window becomes inactive.
    private static readonly HashSet<int> _suppressors = new();

    /// <summary>
    /// Returns true when the tracker should hide because a game UI window
    /// overlaps it. Call once per frame from TrackerWindow.Draw().
    ///
    /// <paramref name="trackerLeft"/>, <paramref name="trackerTop"/>,
    /// <paramref name="trackerRight"/>, <paramref name="trackerBottom"/>
    /// are the tracker's screen-space content bounds in Y-down (ImGui)
    /// coordinates.
    /// </summary>
    public static bool ShouldSuppressTracker(
        float trackerLeft,
        float trackerTop,
        float trackerRight,
        float trackerBottom
    )
    {
        var windows = GetUIWindows();
        if (windows == null || windows.Count == 0)
            return false;

        EnsureCaches(windows.Count);

        for (int i = 0; i < windows.Count; i++)
        {
            var go = windows[i];

            // Window destroyed (scene change) — treat as inactive.
            bool active = go != null && go.activeSelf;

            if (active && !_wasActive![i])
            {
                // Window just opened. Check overlap with cached rect.
                EnsureRect(i, go!);
                if (_rects![i].Overlaps(trackerLeft, trackerTop, trackerRight, trackerBottom))
                    _suppressors.Add(i);
            }
            else if (!active && _wasActive![i])
            {
                // Window just closed. Release suppression.
                _suppressors.Remove(i);
            }

            _wasActive![i] = active;
        }

        return _suppressors.Count > 0;
    }

    /// <summary>
    /// Clear cached rects so they are recomputed on next access. Call when
    /// window positions may have changed: scene load, exit from UI edit mode.
    /// </summary>
    public static void InvalidateRects()
    {
        _rects = null;
        // Don't clear _wasActive or _suppressors — open/close state is
        // still valid. Suppressors will re-evaluate on next open-transition.
    }

    /// <summary>
    /// Full reset. Call on scene change to handle destroyed GameObjects.
    /// </summary>
    public static void Reset()
    {
        _uiWindows = null;
        _searched = false;
        _rects = null;
        _wasActive = null;
        _suppressors.Clear();
    }

    private static List<GameObject>? GetUIWindows()
    {
        if (_uiWindows != null)
            return _uiWindows;
        if (_searched)
            return null;
        _searched = true;

        // Build the union of both game UI window lists.
        // CameraController.UIWindows gates camera rotation;
        // Misc.UIWindows gates the Escape-key close-all sweep.
        // Neither is complete on its own.
        var cam = UnityEngine.Object.FindObjectOfType<CameraController>();
        if (cam == null)
            return null;

        var seen = new HashSet<GameObject>();
        var combined = new List<GameObject>();

        foreach (var w in cam.UIWindows)
            if (w != null && seen.Add(w))
                combined.Add(w);

        if (GameData.Misc != null)
        {
            foreach (var w in GameData.Misc.UIWindows)
                if (w != null && seen.Add(w))
                    combined.Add(w);
        }

        _uiWindows = combined;
        return _uiWindows;
    }

    private static void EnsureCaches(int count)
    {
        if (_wasActive == null || _wasActive.Length != count)
        {
            // First frame or size changed. Initialize wasActive to current
            // state so we don't get false open-transitions on startup.
            _wasActive = new bool[count];
            for (int i = 0; i < count; i++)
            {
                var go = _uiWindows![i];
                _wasActive[i] = go != null && go.activeSelf;
            }
            _suppressors.Clear();
        }

        if (_rects == null || _rects.Length != count)
            _rects = new WindowRect[count];
    }

    /// <summary>
    /// Compute and cache the screen rect for window at index <paramref name="i"/>.
    /// Uses GetWorldCorners + WorldToScreenPoint, then flips Y to Y-down.
    /// </summary>
    private static void EnsureRect(int i, GameObject go)
    {
        if (_rects![i].Right > 0)
            return; // already cached

        var rt = go.GetComponent<RectTransform>();
        if (rt == null)
        {
            // No RectTransform — can't compute rect. Use zero rect
            // which will never overlap anything.
            _rects[i] = default;
            return;
        }

        var corners = new Vector3[4];
        rt.GetWorldCorners(corners);

        float screenH = Screen.height;
        float minX = float.MaxValue,
            maxX = float.MinValue;
        float minY = float.MaxValue,
            maxY = float.MinValue;

        for (int c = 0; c < 4; c++)
        {
            var sp = RectTransformUtility.WorldToScreenPoint(null, corners[c]);
            // Flip Y: Unity Y-up → ImGui Y-down
            float yDown = screenH - sp.y;
            if (sp.x < minX)
                minX = sp.x;
            if (sp.x > maxX)
                maxX = sp.x;
            if (yDown < minY)
                minY = yDown;
            if (yDown > maxY)
                maxY = yDown;
        }

        _rects[i] = new WindowRect
        {
            Left = minX,
            Top = minY,
            Right = maxX,
            Bottom = maxY,
        };
    }
}
