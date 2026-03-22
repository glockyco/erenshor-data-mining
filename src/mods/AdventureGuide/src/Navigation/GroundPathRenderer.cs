using UnityEngine;
using UnityEngine.AI;

namespace AdventureGuide.Navigation;

/// <summary>
/// Renders a ground path from the player to the navigation target using
/// NavMesh.CalculatePath for pathfinding and a Unity LineRenderer for
/// world-space rendering with proper depth occlusion.
///
/// The path is recalculated when the target changes or the player moves
/// beyond a threshold from the last calculation point. Off by default.
///
/// The LineRenderer is created on a hidden child GameObject and destroyed
/// on cleanup. It uses the built-in Sprites/Default shader for a simple
/// colored line that participates in the depth buffer — geometry properly
/// occludes the path.
/// </summary>
public sealed class GroundPathRenderer
{
    private const float RecalcDistance = 5f;
    private const float LineWidth = 0.15f;
    private const float PathYOffset = 0.15f; // lift slightly above ground to avoid z-fighting

    private static readonly Color PathColor = new(1.00f, 0.85f, 0.30f, 0.60f);

    private readonly NavigationController _nav;
    private readonly NavMeshPath _path = new();
    private Vector3[] _corners = new Vector3[64];
    private int _cornerCount;
    private bool _enabled;

    // Track when to recalculate
    private Vector3 _lastCalcPlayerPos;
    private Vector3 _lastCalcTargetPos;
    private bool _pathValid;

    // Unity LineRenderer on a hidden GameObject
    private GameObject? _lineObj;
    private LineRenderer? _line;

    public bool Enabled
    {
        get => _enabled;
        set
        {
            _enabled = value;
            if (_line != null)
                _line.enabled = value && _pathValid;
        }
    }

    public GroundPathRenderer(NavigationController nav)
    {
        _nav = nav;
    }

    /// <summary>
    /// Call each frame. Recalculates the NavMesh path if needed and
    /// updates the LineRenderer positions.
    /// </summary>
    public void Update(string currentScene)
    {
        if (!_enabled || _nav.Target == null)
        {
            _pathValid = false;
            SetLineVisible(false);
            return;
        }

        var playerPos = GameData.PlayerControl?.transform.position;
        if (!playerPos.HasValue)
        {
            SetLineVisible(false);
            return;
        }

        var effectiveTarget = _nav.ZoneLineWaypoint ?? _nav.Target;

        // Only calculate path for same-zone targets
        if (effectiveTarget.IsCrossZone(currentScene))
        {
            _pathValid = false;
            SetLineVisible(false);
            return;
        }

        bool recalculated = RecalculateIfNeeded(playerPos.Value, effectiveTarget.Position);

        if (!_pathValid || _cornerCount < 2)
        {
            SetLineVisible(false);
            return;
        }

        if (recalculated)
            ApplyToLineRenderer();

        SetLineVisible(true);
    }

    public void Destroy()
    {
        if (_lineObj != null)
        {
            UnityEngine.Object.Destroy(_lineObj);
            _lineObj = null;
            _line = null;
        }
    }

    /// <summary>
    /// Returns true if the path was recalculated this frame.
    /// </summary>
    private bool RecalculateIfNeeded(Vector3 playerPos, Vector3 targetPos)
    {
        bool targetMoved = Vector3.Distance(_lastCalcTargetPos, targetPos) > 0.5f;
        bool playerMoved = Vector3.Distance(_lastCalcPlayerPos, playerPos) > RecalcDistance;

        if (_pathValid && !targetMoved && !playerMoved)
            return false;

        _lastCalcPlayerPos = playerPos;
        _lastCalcTargetPos = targetPos;

        _path.ClearCorners();
        _pathValid = NavMesh.CalculatePath(playerPos, targetPos, NavMesh.AllAreas, _path);

        // PathPartial is still useful — show what we have
        if (_path.status == NavMeshPathStatus.PathInvalid)
        {
            _pathValid = false;
            _cornerCount = 0;
            return true;
        }

        // GetCornersNonAlloc avoids the Vector3[] allocation from .corners
        _cornerCount = _path.GetCornersNonAlloc(_corners);
        if (_cornerCount >= _corners.Length)
        {
            // Rare: path has more corners than our buffer. Resize and retry.
            _corners = new Vector3[_cornerCount * 2];
            _cornerCount = _path.GetCornersNonAlloc(_corners);
        }

        return true;
    }

    private void ApplyToLineRenderer()
    {
        EnsureLineRenderer();
        if (_line == null) return;

        _line.positionCount = _cornerCount;
        for (int i = 0; i < _cornerCount; i++)
        {
            // Lift slightly above ground to prevent z-fighting with terrain
            var pos = _corners[i];
            pos.y += PathYOffset;
            _line.SetPosition(i, pos);
        }
    }

    private void EnsureLineRenderer()
    {
        if (_line != null) return;

        _lineObj = new GameObject("AdventureGuide_GroundPath");
        UnityEngine.Object.DontDestroyOnLoad(_lineObj);
        _lineObj.hideFlags = HideFlags.HideAndDontSave;

        _line = _lineObj.AddComponent<LineRenderer>();
        _line.useWorldSpace = true;
        _line.startWidth = LineWidth;
        _line.endWidth = LineWidth;
        _line.numCornerVertices = 4;
        _line.numCapVertices = 2;
        _line.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        _line.receiveShadows = false;
        _line.allowOcclusionWhenDynamic = false;

        // Sprites/Default is a built-in shader that supports vertex colors
        // and renders with proper depth testing
        var mat = new Material(Shader.Find("Sprites/Default"));
        mat.color = PathColor;
        _line.material = mat;
        _line.startColor = PathColor;
        _line.endColor = PathColor;
    }

    private void SetLineVisible(bool visible)
    {
        if (_line != null)
            _line.enabled = visible;
    }
}
