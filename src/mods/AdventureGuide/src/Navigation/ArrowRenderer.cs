using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Renders a screen-space directional arrow pointing toward the navigation
/// target. Uses GL immediate mode (not ImGui DrawList, which crashes after
/// ILRepack due to Vector2 P/Invoke issues).
///
/// When target is off-screen: arrow at screen edge pointing toward it.
/// When target is on-screen: small diamond marker at target position.
/// Distance shown as text via GUI.Label (rendered in OnGUI context).
/// </summary>
public sealed class ArrowRenderer
{
    private const float ArrowSize = 20f;
    private const float EdgeMargin = 40f;
    private const float MarkerSize = 8f;
    private const float ArrivalDistance = 3f;

    private Material? _material;
    private readonly NavigationController _nav;
    private bool _enabled = true;

    // Cached screen info for the GUI.Label pass
    private bool _shouldDrawLabel;
    private Vector2 _labelScreenPos;
    private string _labelText = "";

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
    /// Call from OnRenderObject or Camera.onPostRender. Draws the arrow
    /// using GL immediate mode in screen-space pixel coordinates.
    /// </summary>
    public void RenderGL()
    {
        if (!_enabled || _nav.Target == null || _nav.Distance < ArrivalDistance)
        {
            _shouldDrawLabel = false;
            return;
        }

        EnsureMaterial();
        if (_material == null) return;

        var cam = Camera.main;
        if (cam == null) return;

        // Determine effective target position (zone line waypoint or direct target)
        var effectiveTarget = _nav.ZoneLineWaypoint ?? _nav.Target;
        var targetWorldPos = effectiveTarget.Position;

        // Project target to screen space
        var screenPos = cam.WorldToScreenPoint(targetWorldPos);
        bool isBehind = screenPos.z < 0;
        float sw = Screen.width;
        float sh = Screen.height;

        // Flip if behind camera
        if (isBehind)
        {
            screenPos.x = sw - screenPos.x;
            screenPos.y = sh - screenPos.y;
        }

        // Convert to top-down Y (GL pixel matrix uses bottom-up, but we'll
        // work in bottom-up and only flip for GUI.Label later)
        bool onScreen = !isBehind
            && screenPos.x > EdgeMargin && screenPos.x < sw - EdgeMargin
            && screenPos.y > EdgeMargin && screenPos.y < sh - EdgeMargin;

        GL.PushMatrix();
        GL.LoadPixelMatrix();
        _material.SetPass(0);

        if (onScreen)
        {
            // Draw marker at target position
            DrawDiamond(screenPos.x, screenPos.y, MarkerSize);
            _labelScreenPos = new Vector2(screenPos.x, sh - screenPos.y + MarkerSize + 2f);
        }
        else
        {
            // Clamp to screen edge and draw arrow
            var center = new Vector2(sw * 0.5f, sh * 0.5f);
            var dir = new Vector2(screenPos.x - center.x, screenPos.y - center.y);
            if (dir.sqrMagnitude < 0.01f) dir = Vector2.up;
            dir.Normalize();

            // Clamp to screen bounds with margin
            float halfW = sw * 0.5f - EdgeMargin;
            float halfH = sh * 0.5f - EdgeMargin;

            float tX = dir.x != 0 ? Mathf.Abs(halfW / dir.x) : float.MaxValue;
            float tY = dir.y != 0 ? Mathf.Abs(halfH / dir.y) : float.MaxValue;
            float t = Mathf.Min(tX, tY);

            float ax = center.x + dir.x * t;
            float ay = center.y + dir.y * t;

            DrawArrow(ax, ay, dir);
            _labelScreenPos = new Vector2(ax, sh - ay + ArrowSize + 2f);
        }

        GL.PopMatrix();

        // Prepare label for GUI pass
        _shouldDrawLabel = true;
        string distText = _nav.Distance >= 1000f
            ? $"{_nav.Distance / 1000f:F1}km"
            : $"{Mathf.RoundToInt(_nav.Distance)}m";
        string targetName = effectiveTarget.DisplayName;
        _labelText = _nav.ZoneLineWaypoint != null
            ? $"{targetName}\n{distText}"
            : $"{targetName}\n{distText}";
    }

    /// <summary>
    /// Call from OnGUI to draw the distance label. GL cannot render text,
    /// so we use Unity's IMGUI for that one piece.
    /// </summary>
    public void DrawLabel()
    {
        if (!_shouldDrawLabel || !_enabled) return;

        var style = GUI.skin.label;
        var prevAlignment = style.alignment;
        var prevColor = style.normal.textColor;
        var prevSize = style.fontSize;

        style.alignment = TextAnchor.UpperCenter;
        style.normal.textColor = new Color(1f, 0.95f, 0.6f, 0.95f);
        style.fontSize = 13;

        var size = style.CalcSize(new GUIContent(_labelText));
        var rect = new Rect(
            _labelScreenPos.x - size.x * 0.5f,
            _labelScreenPos.y,
            size.x,
            size.y);
        GUI.Label(rect, _labelText);

        style.alignment = prevAlignment;
        style.normal.textColor = prevColor;
        style.fontSize = prevSize;
    }

    public void Dispose()
    {
        if (_material != null)
            UnityEngine.Object.Destroy(_material);
    }

    // ── GL drawing primitives ──────────────────────────────────────

    private void DrawArrow(float x, float y, Vector2 dir)
    {
        // Arrow triangle pointing in direction of target
        float angle = Mathf.Atan2(dir.y, dir.x);
        float cos = Mathf.Cos(angle);
        float sin = Mathf.Sin(angle);

        // Triangle vertices: tip, left base, right base
        float tipX = x + cos * ArrowSize;
        float tipY = y + sin * ArrowSize;

        float perpX = -sin * ArrowSize * 0.5f;
        float perpY = cos * ArrowSize * 0.5f;

        float baseX = x - cos * ArrowSize * 0.3f;
        float baseY = y - sin * ArrowSize * 0.3f;

        // Filled triangle — warm gold color
        GL.Begin(GL.TRIANGLES);
        GL.Color(new Color(1f, 0.85f, 0.3f, 0.9f));
        GL.Vertex3(tipX, tipY, 0);
        GL.Vertex3(baseX + perpX, baseY + perpY, 0);
        GL.Vertex3(baseX - perpX, baseY - perpY, 0);
        GL.End();

        // Dark outline for contrast
        GL.Begin(GL.LINES);
        GL.Color(new Color(0.1f, 0.1f, 0.1f, 0.8f));
        GL.Vertex3(tipX, tipY, 0);
        GL.Vertex3(baseX + perpX, baseY + perpY, 0);
        GL.Vertex3(baseX + perpX, baseY + perpY, 0);
        GL.Vertex3(baseX - perpX, baseY - perpY, 0);
        GL.Vertex3(baseX - perpX, baseY - perpY, 0);
        GL.Vertex3(tipX, tipY, 0);
        GL.End();
    }

    private void DrawDiamond(float x, float y, float size)
    {
        GL.Begin(GL.TRIANGLES);
        GL.Color(new Color(1f, 0.85f, 0.3f, 0.9f));
        // Top triangle
        GL.Vertex3(x, y + size, 0);
        GL.Vertex3(x - size, y, 0);
        GL.Vertex3(x + size, y, 0);
        // Bottom triangle
        GL.Vertex3(x, y - size, 0);
        GL.Vertex3(x + size, y, 0);
        GL.Vertex3(x - size, y, 0);
        GL.End();

        // Outline
        GL.Begin(GL.LINES);
        GL.Color(new Color(0.1f, 0.1f, 0.1f, 0.8f));
        GL.Vertex3(x, y + size, 0);
        GL.Vertex3(x + size, y, 0);
        GL.Vertex3(x + size, y, 0);
        GL.Vertex3(x, y - size, 0);
        GL.Vertex3(x, y - size, 0);
        GL.Vertex3(x - size, y, 0);
        GL.Vertex3(x - size, y, 0);
        GL.Vertex3(x, y + size, 0);
        GL.End();
    }

    private void EnsureMaterial()
    {
        if (_material != null) return;
        // Unlit colored material for GL drawing
        var shader = Shader.Find("Hidden/Internal-Colored");
        if (shader == null) return;
        _material = new Material(shader)
        {
            hideFlags = HideFlags.HideAndDontSave
        };
        _material.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
        _material.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
        _material.SetInt("_Cull", (int)UnityEngine.Rendering.CullMode.Off);
        _material.SetInt("_ZWrite", 0);
        _material.SetInt("_ZTest", (int)UnityEngine.Rendering.CompareFunction.Always);
    }
}
