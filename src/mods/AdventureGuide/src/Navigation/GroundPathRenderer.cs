using AdventureGuide.Rendering;
using AdventureGuide.UI;
using UnityEngine;
using UnityEngine.AI;
using V2 = AdventureGuide.Rendering.CimguiNative.Vec2;

namespace AdventureGuide.Navigation;

/// <summary>
/// Renders a ground path from the player to the navigation target using
/// NavMesh.CalculatePath for pathfinding and ImGui's background draw list
/// for screen-space line rendering.
///
/// The path is recalculated when the target changes or the player moves
/// beyond a threshold from the last calculation point. Off by default.
///
/// Renders during the ImGui layout pass alongside ArrowRenderer — no
/// separate GL pipeline or Camera.onPostRender callback.
/// </summary>
public sealed class GroundPathRenderer
{
    private const float RecalcDistance = 5f;
    private const float LineThickness = 2.5f;
    private const float DotRadius = 3f;
    private const float DotSpacing = 20f; // screen-space pixels between dots

    private static readonly uint ColorPath = Theme.Rgba(1.00f, 0.85f, 0.30f, 0.50f);
    private static readonly uint ColorDot = Theme.Rgba(1.00f, 0.85f, 0.30f, 0.70f);

    private readonly NavigationController _nav;
    private readonly NavMeshPath _path = new();
    private Vector3[] _corners = new Vector3[64];
    private int _cornerCount;
    private bool _enabled;

    // Track when to recalculate
    private Vector3 _lastCalcPlayerPos;
    private Vector3 _lastCalcTargetPos;
    private bool _pathValid;

    public bool Enabled
    {
        get => _enabled;
        set => _enabled = value;
    }

    public GroundPathRenderer(NavigationController nav)
    {
        _nav = nav;
    }

    /// <summary>
    /// Call during the ImGui layout pass. Calculates the NavMesh path if
    /// needed, then projects path corners to screen space and draws them
    /// on the background draw list.
    /// </summary>
    public void Draw(string currentScene)
    {
        if (!_enabled || _nav.Target == null)
        {
            _pathValid = false;
            return;
        }

        var cam = CameraCache.Get();
        if (cam == null) return;

        var playerPos = GameData.PlayerControl?.transform.position;
        if (!playerPos.HasValue) return;

        var effectiveTarget = _nav.ZoneLineWaypoint ?? _nav.Target;

        // Only calculate path for same-zone targets
        if (effectiveTarget.IsCrossZone(currentScene))
        {
            _pathValid = false;
            return;
        }

        RecalculateIfNeeded(playerPos.Value, effectiveTarget.Position);

        if (!_pathValid || _cornerCount < 2)
            return;

        var drawList = CimguiNative.igGetBackgroundDrawList_Nil();
        if (drawList == System.IntPtr.Zero) return;

        DrawPath(drawList, cam);
    }

    private void RecalculateIfNeeded(Vector3 playerPos, Vector3 targetPos)
    {
        bool targetMoved = Vector3.Distance(_lastCalcTargetPos, targetPos) > 0.5f;
        bool playerMoved = Vector3.Distance(_lastCalcPlayerPos, playerPos) > RecalcDistance;

        if (_pathValid && !targetMoved && !playerMoved)
            return;

        _lastCalcPlayerPos = playerPos;
        _lastCalcTargetPos = targetPos;

        _path.ClearCorners();
        _pathValid = NavMesh.CalculatePath(playerPos, targetPos, NavMesh.AllAreas, _path);

        // PathPartial is still useful — show what we have
        if (_path.status == NavMeshPathStatus.PathInvalid)
        {
            _pathValid = false;
            _cornerCount = 0;
            return;
        }

        // GetCornersNonAlloc avoids the Vector3[] allocation from .corners
        _cornerCount = _path.GetCornersNonAlloc(_corners);
        if (_cornerCount >= _corners.Length)
        {
            // Rare: path has more corners than our buffer. Resize and retry.
            _corners = new Vector3[_cornerCount * 2];
            _cornerCount = _path.GetCornersNonAlloc(_corners);
        }
    }

    private void DrawPath(System.IntPtr drawList, Camera cam)
    {
        float sh = Screen.height;

        for (int i = 0; i < _cornerCount - 1; i++)
        {
            var sp1 = cam.WorldToScreenPoint(_corners[i]);
            var sp2 = cam.WorldToScreenPoint(_corners[i + 1]);

            // Skip segments entirely behind camera
            if (sp1.z < 0 && sp2.z < 0) continue;

            // Skip segments where one endpoint is behind camera — projection
            // is unreliable and produces wild screen coordinates
            if (sp1.z < 0 || sp2.z < 0) continue;

            // Convert to ImGui Y (top-down)
            float y1 = sh - sp1.y;
            float y2 = sh - sp2.y;

            var p1 = new V2(sp1.x, y1);
            var p2 = new V2(sp2.x, y2);

            CimguiNative.ImDrawList_AddLine(drawList, p1, p2, ColorPath, LineThickness);

            // Draw dots along the segment for better ground-path visibility
            DrawDotsAlongSegment(drawList, p1, p2);
        }
    }

    /// <summary>
    /// Evenly space small filled circles along a screen-space line segment.
    /// Gives the path a dotted/breadcrumb appearance that reads better than
    /// a solid line in 3D perspective projection.
    /// </summary>
    private static void DrawDotsAlongSegment(System.IntPtr drawList, V2 p1, V2 p2)
    {
        float dx = p2.X - p1.X;
        float dy = p2.Y - p1.Y;
        float segLen = Mathf.Sqrt(dx * dx + dy * dy);

        if (segLen < DotSpacing) return;

        int dotCount = Mathf.FloorToInt(segLen / DotSpacing);
        for (int d = 1; d <= dotCount; d++)
        {
            float t = d / (float)(dotCount + 1);
            var dot = new V2(p1.X + dx * t, p1.Y + dy * t);
            CimguiNative.ImDrawList_AddCircleFilled(drawList, dot, DotRadius, ColorDot, 6);
        }
    }
}
