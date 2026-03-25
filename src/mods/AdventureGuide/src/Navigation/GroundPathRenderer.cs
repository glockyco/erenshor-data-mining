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
/// Visual style: dashes with soft edges and a subtle glow halo. Two
/// layered LineRenderers — a wider dim halo underneath and a bright
/// dashed core on top. Path corners are offset above the NavMesh
/// surface to reduce ground clipping.
/// </summary>
public sealed class GroundPathRenderer
{
    private const float RecalcDistance = 5f;
    private const float ArrivalDistance = 15f;
    private const float CoreWidth = 0.20f;
    private const float GlowWidth = 0.50f;
    private const float PathYOffset = 0.40f;
    private const float TileScale = 1.5f; // dashes per world unit

    // Bright gold core, dimmer translucent glow
    private static readonly Color CoreColor = new(1.00f, 0.85f, 0.30f, 0.80f);
    private static readonly Color GlowColor = new(1.00f, 0.75f, 0.20f, 0.15f);

    private readonly NavigationController _nav;
    private readonly NavMeshPath _path = new();
    private Vector3[] _corners = new Vector3[64];
    private int _cornerCount;
    private bool _enabled;

    // Track when to recalculate
    private Vector3 _lastCalcPlayerPos;
    private Vector3 _lastCalcTargetPos;
    private bool _pathValid;

    // Two layered LineRenderers: glow halo + dashed core
    private GameObject? _lineObj;
    private LineRenderer? _core;
    private LineRenderer? _glow;
    private Material? _coreMat;

    public bool Enabled
    {
        get => _enabled;
        set
        {
            _enabled = value;
            SetLineVisible(value && _pathValid);
        }
    }

    public GroundPathRenderer(NavigationController nav)
    {
        _nav = nav;
    }

    /// <summary>
    /// Call each frame. Recalculates the NavMesh path if needed,
    /// updates LineRenderer positions, and animates the dash scroll.
    /// </summary>
    public void Update(string currentScene)
    {
        if (!_enabled || _nav.Target == null)
        {
            _pathValid = false;
            SetLineVisible(false);
            return;
        }

        if (GameData.PlayerControl == null)
        {
            SetLineVisible(false);
            return;
        }
        var playerPos = GameData.PlayerControl.transform.position;

        var effectiveTarget = _nav.ZoneLineWaypoint ?? _nav.Target;

        // Only calculate path for same-zone targets
        if (effectiveTarget.IsCrossZone(currentScene))
        {
            _pathValid = false;
            SetLineVisible(false);
            return;
        }

        // Hide path when close to target
        if (_nav.Distance < ArrivalDistance)
        {
            _pathValid = false;
            SetLineVisible(false);
            return;
        }

        bool recalculated = RecalculateIfNeeded(playerPos, effectiveTarget.Position);

        if (!_pathValid || _cornerCount < 2)
        {
            SetLineVisible(false);
            return;
        }

        if (recalculated)
            ApplyToLineRenderers();

        SetLineVisible(true);
    }

    public void Destroy()
    {
        if (_lineObj != null)
        {
            UnityEngine.Object.Destroy(_lineObj);
            _lineObj = null;
            _core = null;
            _glow = null;
            _coreMat = null;
        }
    }

    private bool RecalculateIfNeeded(Vector3 playerPos, Vector3 targetPos)
    {
        bool targetMoved = Vector3.Distance(_lastCalcTargetPos, targetPos) > 0.5f;
        bool playerMoved = Vector3.Distance(_lastCalcPlayerPos, playerPos) > RecalcDistance;

        if (_pathValid && !targetMoved && !playerMoved)
            return false;

        // Snap player position to the NavMesh surface. Without this, an
        // airborne player (jumping, falling) produces an off-mesh source
        // position that makes CalculatePath fail, hiding the path mid-jump.
        if (!NavMesh.SamplePosition(playerPos, out var navHit, 5f, NavMesh.AllAreas))
        {
            // Player is too far from any NavMesh surface — keep showing the
            // last valid path rather than hiding it.
            return false;
        }

        _lastCalcPlayerPos = playerPos;
        _lastCalcTargetPos = targetPos;

        // Snap target position to NavMesh surface too. Directly-placed
        // objects like mining nodes often sit on terrain geometry outside
        // the NavMesh, causing CalculatePath to fail.
        var pathTarget = targetPos;
        if (NavMesh.SamplePosition(targetPos, out var targetNavHit, 5f, NavMesh.AllAreas))
            pathTarget = targetNavHit.position;

        _path.ClearCorners();
        bool pathFound = NavMesh.CalculatePath(navHit.position, pathTarget, NavMesh.AllAreas, _path);

        if (!pathFound || _path.status == NavMeshPathStatus.PathInvalid)
        {
            // Target unreachable — hide the stale path so it doesn't
            // mislead the player by pointing at a previous target.
            _pathValid = false;
            return true; // signal recalculation happened (path cleared)
        }

        _pathValid = true;
        _cornerCount = _path.GetCornersNonAlloc(_corners);
        if (_cornerCount >= _corners.Length)
        {
            _corners = new Vector3[_cornerCount * 2];
            _cornerCount = _path.GetCornersNonAlloc(_corners);
        }

        return true;
    }

    private void ApplyToLineRenderers()
    {
        EnsureLineRenderers();
        if (_core == null || _glow == null) return;

        _core.positionCount = _cornerCount;
        _glow.positionCount = _cornerCount;
        for (int i = 0; i < _cornerCount; i++)
        {
            var pos = _corners[i];
            pos.y += PathYOffset;
            _core.SetPosition(i, pos);

            // Glow sits slightly below core to avoid z-fighting between layers
            var glowPos = pos;
            glowPos.y -= 0.01f;
            _glow.SetPosition(i, glowPos);
        }

        // Set texture tiling based on path length so dash density is consistent
        float pathLen = 0f;
        for (int i = 0; i < _cornerCount - 1; i++)
            pathLen += Vector3.Distance(_corners[i], _corners[i + 1]);

        if (_coreMat != null)
            _coreMat.mainTextureScale = new Vector2(pathLen * TileScale, 1f);
    }
    // ── LineRenderer setup ────────────────────────────────────────

    private void EnsureLineRenderers()
    {
        if (_core != null) return;

        _lineObj = new GameObject("AdventureGuide_GroundPath");
        UnityEngine.Object.DontDestroyOnLoad(_lineObj);
        _lineObj.hideFlags = HideFlags.HideAndDontSave;

        // Bottom layer: soft glow halo
        var glowObj = new GameObject("Glow");
        glowObj.transform.SetParent(_lineObj.transform);
        _glow = glowObj.AddComponent<LineRenderer>();
        ConfigureLineRenderer(_glow, GlowWidth);
        var glowMat = new Material(Shader.Find("Sprites/Default"));
        glowMat.color = GlowColor;
        _glow.material = glowMat;
        _glow.startColor = GlowColor;
        _glow.endColor = GlowColor;

        // Top layer: bright dashed core
        var coreObj = new GameObject("Core");
        coreObj.transform.SetParent(_lineObj.transform);
        _core = coreObj.AddComponent<LineRenderer>();
        ConfigureLineRenderer(_core, CoreWidth);

        _coreMat = new Material(Shader.Find("Sprites/Default"));
        _coreMat.mainTexture = CreateDashTexture();
        _coreMat.color = Color.white; // tint via vertex colors instead
        _core.material = _coreMat;
        _core.textureMode = LineTextureMode.Tile;
        _core.startColor = CoreColor;
        _core.endColor = CoreColor;
    }

    private static void ConfigureLineRenderer(LineRenderer lr, float width)
    {
        lr.useWorldSpace = true;
        lr.startWidth = width;
        lr.endWidth = width;
        lr.numCornerVertices = 4;
        lr.numCapVertices = 2;
        lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        lr.receiveShadows = false;
        lr.allowOcclusionWhenDynamic = false;
    }

    /// <summary>
    /// Create a 128x4 procedural dash texture: a smooth-edged dash fading
    /// to transparent, followed by a gap. Wrapped horizontally so it tiles
    /// seamlessly along the LineRenderer.
    /// </summary>
    private static Texture2D CreateDashTexture()
    {
        const int width = 128;
        const int height = 4;
        const float dashFraction = 0.55f; // portion of tile that is the dash
        const float fadeZone = 0.10f;     // smooth fade at dash edges

        var tex = new Texture2D(width, height, TextureFormat.RGBA32, false);
        tex.wrapMode = TextureWrapMode.Repeat;
        tex.filterMode = FilterMode.Bilinear;

        var pixels = new Color[width * height];
        for (int x = 0; x < width; x++)
        {
            float t = (float)x / width;
            float alpha;

            if (t < fadeZone)
            {
                // Fade in at dash start
                alpha = t / fadeZone;
            }
            else if (t < dashFraction - fadeZone)
            {
                // Full dash body
                alpha = 1f;
            }
            else if (t < dashFraction)
            {
                // Fade out at dash end
                alpha = (dashFraction - t) / fadeZone;
            }
            else
            {
                // Gap
                alpha = 0f;
            }

            var c = new Color(1f, 1f, 1f, alpha);
            for (int y = 0; y < height; y++)
                pixels[y * width + x] = c;
        }

        tex.SetPixels(pixels);
        tex.Apply(false, true); // makeNoLongerReadable for GPU memory
        return tex;
    }

    private void SetLineVisible(bool visible)
    {
        if (_core != null) _core.enabled = visible;
        if (_glow != null) _glow.enabled = visible;
    }
}
