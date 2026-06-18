using AdventureGuide.Rendering;
using AdventureGuide.UI;
using UnityEngine;
using V2 = AdventureGuide.Rendering.CimguiNative.Vec2;

namespace AdventureGuide.Navigation;

/// <summary>
/// Renders a screen-space directional arrow pointing toward the navigation
/// target using ImGui's foreground draw list via raw cimgui P/Invoke.
///
/// Draws during the ImGui layout pass — no separate GL pipeline, no
/// Camera.onPostRender, no GUI.Label. Everything goes through ImGui's
/// existing CommandBuffer rendering path.
///
/// When target is off-screen: arrow at screen edge pointing toward it.
/// When target is on-screen: diamond marker at target position.
/// Distance and name rendered as text via DrawList.AddText.
/// </summary>
public sealed class ArrowRenderer
{
    private const float ArrowSize = 20f;
    private const float EdgeMargin = 40f;
    private const float MarkerSize = 8f;
    private const float ArrivalDistance = 15f;
    private const float OutlineThickness = 1.5f;

    private static readonly uint ColorArrow = Theme.Rgba(1.00f, 0.85f, 0.30f, 0.90f);
    private static readonly uint ColorOutline = Theme.Rgba(0.10f, 0.10f, 0.10f, 0.80f);
    private static readonly uint ColorText = Theme.Rgba(1.00f, 0.95f, 0.60f, 0.95f);

    private readonly NavigationController _nav;
    private bool _enabled = true;

    // Cached label lines — each line centered independently for multi-line text
    private string[] _cachedLines = System.Array.Empty<string>();
    private CimguiNative.Vec2[] _cachedLineSizes = System.Array.Empty<CimguiNative.Vec2>();
    private float _cachedTotalHeight;
    private int _cachedDistInt = -1;
    private string? _cachedTargetName;

    public bool Enabled
    {
        get => _enabled;
        set => _enabled = value;
    }

    public ArrowRenderer(NavigationController nav)
    {
        _nav = nav;
    }

    /// <summary>
    /// Call during the ImGui layout pass (OnLayout callback).
    /// Draws the navigation arrow on the foreground draw list.
    /// </summary>
    public void Draw()
    {
        if (!_enabled || _nav.Target == null || _nav.Distance < ArrivalDistance)
            return;

        var drawList = CimguiNative.igGetBackgroundDrawList_Nil();
        if (drawList == System.IntPtr.Zero) return;

        var cam = CameraCache.Get();
        if (cam == null) return;

        var effectiveTarget = _nav.ZoneLineWaypoint ?? _nav.Target;
        var screenPos = cam.WorldToScreenPoint(effectiveTarget.Position + Vector3.up * NavigationDisplay.GroundOffset);
        bool isBehind = screenPos.z < 0;
        float sw = Screen.width;
        float sh = Screen.height;

        // Flip if behind camera
        if (isBehind)
        {
            screenPos.x = sw - screenPos.x;
            screenPos.y = sh - screenPos.y;
        }

        // ImGui uses top-down Y (0 = top of screen)
        float imguiY = sh - screenPos.y;

        bool onScreen = !isBehind
            && screenPos.x > EdgeMargin && screenPos.x < sw - EdgeMargin
            && imguiY > EdgeMargin && imguiY < sh - EdgeMargin;

        // Rebuild label only when the visible distance or target name changes
        int distInt = Mathf.RoundToInt(_nav.Distance);
        if (distInt != _cachedDistInt || effectiveTarget.DisplayName != _cachedTargetName)
        {
            _cachedDistInt = distInt;
            _cachedTargetName = effectiveTarget.DisplayName;

            // Split into lines; distance goes on the first line
            var rawLines = effectiveTarget.DisplayName.Split('\n');
            rawLines[0] = $"{rawLines[0]} ({distInt}m)";
            _cachedLines = rawLines;
            _cachedLineSizes = new CimguiNative.Vec2[rawLines.Length];
            _cachedTotalHeight = 0;
            for (int i = 0; i < rawLines.Length; i++)
            {
                _cachedLineSizes[i] = CimguiNative.CalcTextSize(rawLines[i]);
                _cachedTotalHeight += _cachedLineSizes[i].Y;
            }
        }

        if (onScreen)
        {
            DrawDiamond(drawList, screenPos.x, imguiY, MarkerSize);
            DrawCenteredLines(drawList, screenPos.x, imguiY + MarkerSize + 4f, sw);
        }
        else
        {
            // Clamp to screen edge
            var centerX = sw * 0.5f;
            var centerY = sh * 0.5f;
            float dirX = screenPos.x - centerX;
            float dirY = imguiY - centerY;
            float dirLen = Mathf.Sqrt(dirX * dirX + dirY * dirY);
            if (dirLen < 0.01f) { dirX = 0; dirY = -1; dirLen = 1; }
            dirX /= dirLen;
            dirY /= dirLen;

            // Margin accounts for arrow size so tip stays on screen
            float margin = EdgeMargin + ArrowSize;
            float halfW = sw * 0.5f - margin;
            float halfH = sh * 0.5f - margin;

            float tX = dirX != 0 ? Mathf.Abs(halfW / dirX) : float.MaxValue;
            float tY = dirY != 0 ? Mathf.Abs(halfH / dirY) : float.MaxValue;
            float t = Mathf.Min(tX, tY);

            float ax = centerX + dirX * t;
            float ay = centerY + dirY * t;

            DrawArrow(drawList, ax, ay, dirX, dirY);
            DrawCenteredLines(drawList, ax, ay + ArrowSize + 4f, sw);
        }
    }

    // No resources to dispose — DrawList is owned by ImGui
    public void Dispose() { }

    /// <summary>Draw each cached line centered independently on anchorX.</summary>
    private void DrawCenteredLines(System.IntPtr dl, float anchorX, float y, float screenWidth)
    {
        const float pad = EdgeMargin;
        for (int i = 0; i < _cachedLines.Length; i++)
        {
            float x = anchorX - _cachedLineSizes[i].X * 0.5f;
            if (x < pad) x = pad;
            if (x + _cachedLineSizes[i].X > screenWidth - pad)
                x = screenWidth - pad - _cachedLineSizes[i].X;
            CimguiNative.AddText(dl, x, y, ColorText, _cachedLines[i]);
            y += _cachedLineSizes[i].Y;
        }
    }

    // ── Drawing primitives ─────────────────────────────────────────

    private static void DrawArrow(System.IntPtr dl, float x, float y, float dirX, float dirY)
    {
        float angle = Mathf.Atan2(dirY, dirX);
        float cos = Mathf.Cos(angle);
        float sin = Mathf.Sin(angle);

        // Triangle: tip extends in direction, base is behind
        float tipX = x + cos * ArrowSize;
        float tipY = y + sin * ArrowSize;

        float perpX = -sin * ArrowSize * 0.5f;
        float perpY = cos * ArrowSize * 0.5f;

        float baseX = x - cos * ArrowSize * 0.3f;
        float baseY = y - sin * ArrowSize * 0.3f;

        var tip = new V2(tipX, tipY);
        var left = new V2(baseX + perpX, baseY + perpY);
        var right = new V2(baseX - perpX, baseY - perpY);

        CimguiNative.ImDrawList_AddTriangleFilled(dl, tip, left, right, ColorArrow);
        CimguiNative.ImDrawList_AddTriangle(dl, tip, left, right, ColorOutline, OutlineThickness);
    }

    private static void DrawDiamond(System.IntPtr dl, float x, float y, float size)
    {
        var top = new V2(x, y - size);
        var right = new V2(x + size, y);
        var bottom = new V2(x, y + size);
        var left = new V2(x - size, y);

        CimguiNative.ImDrawList_AddQuadFilled(dl, top, right, bottom, left, ColorArrow);
        // Outline via four lines for clean anti-aliased edges
        CimguiNative.ImDrawList_AddLine(dl, top, right, ColorOutline, OutlineThickness);
        CimguiNative.ImDrawList_AddLine(dl, right, bottom, ColorOutline, OutlineThickness);
        CimguiNative.ImDrawList_AddLine(dl, bottom, left, ColorOutline, OutlineThickness);
        CimguiNative.ImDrawList_AddLine(dl, left, top, ColorOutline, OutlineThickness);
    }
}
