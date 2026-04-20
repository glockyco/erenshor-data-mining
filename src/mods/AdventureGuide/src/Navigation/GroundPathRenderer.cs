using AdventureGuide.Diagnostics;
using UnityEngine;
using UnityEngine.AI;

namespace AdventureGuide.Navigation;

/// <summary>
/// Renders a ground path from the player to the navigation target using
/// NavMesh.CalculatePath for pathfinding and three independent LineRenderer
/// pairs for world-space rendering with proper depth occlusion.
///
/// The path is split into three segments to prevent visual noise from texture
/// rescaling as the player moves. Each segment has its own material and
/// computes its own tiling independently, so movement in one segment does not
/// disturb the dash pattern in any other.
///
///   Stub: first NavMesh node → player   (texture anchors at the stable node)
///   Mid:  first node → last node        (fully stable between recalculations)
///   Tail: last NavMesh node → target    (texture anchors at the stable node)
///
/// Interior corners are lifted above the NavMesh surface to reduce ground
/// clipping. The player and target endpoints sit at their raw world positions
/// so they connect cleanly to the arrow marker and the player's feet.
///
/// When the path has no interior nodes (N=2), a single stub segment covers
/// the direct line. When there is exactly one interior node (N=3), stub and
/// tail share that node and mid is suppressed.
/// </summary>
internal sealed class GroundPathRenderer
{
    private const float RecalcDistance = 5f;
    private const float PlayerNavSampleRadius = 5f;
    private const float TargetNavSampleRadius = 15f;
    private const float ArrivalDistance = 15f;
    private const float CoreWidth = 0.20f;
    private const float GlowWidth = 0.50f;
    private const float TileScale = 1.5f; // dashes per world unit

    // Bright gold core, dimmer translucent glow
    private static readonly Color CoreColor = new(1.00f, 0.85f, 0.30f, 0.80f);
    private static readonly Color GlowColor = new(1.00f, 0.75f, 0.20f, 0.15f);

    private readonly NavigationEngine _nav;
    private readonly DiagnosticsCore? _diagnostics;
    private readonly NavMeshPath _path = new();
    private Vector3[] _corners = new Vector3[64];
    private int _cornerCount;
    private bool _enabled;

    // Track when to recalculate
    private Vector3 _lastCalcPlayerPos;
    private Vector3 _lastCalcTargetPos;
    private bool _pathValid;

    // Three independent segments; created on first use
    private GameObject? _lineObj;
    private PathSegment? _stub;
    private PathSegment? _mid;
    private PathSegment? _tail;

    public bool Enabled
    {
        get => _enabled;
        set
        {
            _enabled = value;
            SetAllVisible(value && _pathValid);
        }
    }

    public GroundPathRenderer(NavigationEngine nav, DiagnosticsCore? diagnostics = null)
    {
        _nav = nav;
        _diagnostics = diagnostics;
    }

    /// <summary>
    /// Call each frame. Recalculates the NavMesh path when needed,
    /// distributes corners across the three segments on recalculation,
    /// and updates the dynamic endpoints every frame.
    /// </summary>
    public void Update()
    {
        using var _span = _diagnostics.OpenSpan(DiagnosticSpanKind.GroundPathUpdate);

        if (!_enabled || !_nav.HasTarget)
        {
            _pathValid = false;
            SetAllVisible(false);
            return;
        }

        if (GameData.PlayerControl == null)
        {
            SetAllVisible(false);
            return;
        }
        var playerPos = GameData.PlayerControl.transform.position;

        var effectiveTarget = _nav.EffectiveTarget!.Value;

        // Hide path when close to target
        if (_nav.Distance < ArrivalDistance)
        {
            _pathValid = false;
            SetAllVisible(false);
            return;
        }

        bool recalculated = RecalculateIfNeeded(playerPos, effectiveTarget);

        if (!_pathValid || _cornerCount < 2)
        {
            SetAllVisible(false);
            return;
        }

        if (recalculated)
            ApplyToSegments();

        // Update only the moving endpoints every frame — the stable mid
        // segment and the anchor positions of stub/tail are untouched.
        UpdateEndpoints(playerPos, effectiveTarget);
        SetAllVisible(true);
    }

    public void Destroy()
    {
        if (_lineObj != null)
        {
            UnityEngine.Object.Destroy(_lineObj);
            _lineObj = null;
            _stub = null;
            _mid = null;
            _tail = null;
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
        if (
            !NavMesh.SamplePosition(
                playerPos,
                out var navHit,
                PlayerNavSampleRadius,
                NavMesh.AllAreas
            )
        )
        {
            // Player is too far from any NavMesh surface — keep showing the
            // last valid path rather than hiding it.
            return false;
        }

        _lastCalcPlayerPos = playerPos;
        _lastCalcTargetPos = targetPos;

        // Snap target position to NavMesh surface too. Zone lines and
        // directly-placed objects (mining nodes) often sit on terrain
        // geometry outside the NavMesh, causing CalculatePath to fail.
        // Larger radius than player snap since targets can be further
        // from walkable surfaces.
        var pathTarget = targetPos;
        if (
            NavMesh.SamplePosition(
                targetPos,
                out var targetNavHit,
                TargetNavSampleRadius,
                NavMesh.AllAreas
            )
        )
            pathTarget = targetNavHit.position;

        _path.ClearCorners();
        bool pathFound = NavMesh.CalculatePath(
            navHit.position,
            pathTarget,
            NavMesh.AllAreas,
            _path
        );

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

    /// <summary>
    /// Distribute the current NavMesh corners across the three segments.
    /// Called only when the path has been recalculated. UpdateEndpoints
    /// will immediately run after to fill in the dynamic player/target ends.
    /// </summary>
    private void ApplyToSegments()
    {
        EnsureSegments();

        if (_cornerCount == 2)
        {
            // No interior nodes: direct line. Both endpoints are dynamic;
            // UpdateEndpoints fills them with playerPos and targetPos.
            _stub!.SetEndpoints(Vector3.zero, Vector3.zero);
            _mid!.Clear();
            _tail!.Clear();
            return;
        }

        int firstNode = 1;
        int lastNode = _cornerCount - 2;

        // Stub: anchor at firstNode (stable), player end filled by UpdateEndpoints.
        var firstAnchor = _corners[firstNode];
        firstAnchor.y += NavigationDisplay.GroundOffset;
        _stub!.SetEndpoints(firstAnchor, firstAnchor); // player placeholder

        // Tail: anchor at lastNode (stable), target end filled by UpdateEndpoints.
        var lastAnchor = _corners[lastNode];
        lastAnchor.y += NavigationDisplay.GroundOffset;
        _tail!.SetEndpoints(lastAnchor, lastAnchor); // target placeholder

        // Mid: all interior nodes. Completely stable between recalculations.
        // Suppressed when firstNode == lastNode (N=3, single shared anchor).
        if (firstNode < lastNode)
            _mid!.SetFromCorners(
                _corners,
                firstNode,
                lastNode - firstNode + 1,
                NavigationDisplay.GroundOffset
            );
        else
            _mid!.Clear();
    }

    /// <summary>
    /// Overwrite the moving endpoints of stub and tail each frame.
    /// The stable anchor at position 0 of each segment is untouched,
    /// so the dash pattern stays locked there as the endpoints shift.
    /// </summary>
    private void UpdateEndpoints(Vector3 playerPos, Vector3 targetPos)
    {
        if (_stub == null || _cornerCount < 2)
            return;

        var elevatedPlayer = playerPos + Vector3.up * NavigationDisplay.GroundOffset;
        var elevatedTarget = targetPos + Vector3.up * NavigationDisplay.GroundOffset;

        if (_cornerCount == 2)
        {
            // No interior nodes: anchor at target (moves less), player end is dynamic.
            _stub.SetEndpoints(elevatedTarget, elevatedPlayer);
            return;
        }

        _stub.UpdateLastPosition(elevatedPlayer);
        _tail!.UpdateLastPosition(elevatedTarget);
    }

    // ── Segment management ────────────────────────────────────────

    private void EnsureSegments()
    {
        if (_stub != null)
            return;

        _lineObj = new GameObject("AdventureGuide_GroundPath");
        UnityEngine.Object.DontDestroyOnLoad(_lineObj);
        _lineObj.hideFlags = HideFlags.HideAndDontSave;

        // All three segments share the same dash texture (one GPU upload),
        // but each gets its own Material so tiling is independent.
        var dashTex = CreateDashTexture();
        _stub = new PathSegment(_lineObj, "Stub", dashTex);
        _mid = new PathSegment(_lineObj, "Mid", dashTex);
        _tail = new PathSegment(_lineObj, "Tail", dashTex);
    }

    private void SetAllVisible(bool visible)
    {
        _stub?.SetVisible(visible);
        _mid?.SetVisible(visible);
        _tail?.SetVisible(visible);
    }

    // ── PathSegment ───────────────────────────────────────────────

    /// <summary>
    /// One visual segment: a core (dashed gold) and glow (wider dim halo)
    /// LineRenderer pair with an independent tiling material instance.
    ///
    /// Tiling is recomputed locally whenever positions change, so no segment
    /// affects the dash scale of any other. The texture anchors at position 0
    /// (the stable NavMesh node for stub/tail), so the pattern stays locked
    /// there as the dynamic endpoint at position N-1 shifts each frame.
    /// </summary>
    private sealed class PathSegment
    {
        private readonly LineRenderer _core;
        private readonly LineRenderer _glow;
        private readonly Material _coreMat;
        private Vector3 _anchor; // cached position[0] for per-frame length recompute

        internal PathSegment(GameObject parent, string name, Texture2D dashTex)
        {
            // Bottom layer: soft glow halo
            var glowObj = new GameObject($"{name}_Glow");
            glowObj.transform.SetParent(parent.transform);
            _glow = glowObj.AddComponent<LineRenderer>();
            ConfigureLineRenderer(_glow, GlowWidth);
            var glowMat = new Material(Shader.Find("Sprites/Default"));
            glowMat.color = GlowColor;
            _glow.material = glowMat;
            _glow.startColor = GlowColor;
            _glow.endColor = GlowColor;

            // Top layer: bright dashed core
            var coreObj = new GameObject($"{name}_Core");
            coreObj.transform.SetParent(parent.transform);
            _core = coreObj.AddComponent<LineRenderer>();
            ConfigureLineRenderer(_core, CoreWidth);
            _coreMat = new Material(Shader.Find("Sprites/Default"));
            _coreMat.mainTexture = dashTex;
            _coreMat.color = Color.white; // tint via vertex colors
            _core.material = _coreMat;
            _core.textureMode = LineTextureMode.Tile;
            _core.startColor = CoreColor;
            _core.endColor = CoreColor;
        }

        /// <summary>
        /// Set a two-point segment. Used for stub/tail anchor initialization
        /// and the N=2 direct-line fallback. The anchor (position 0) is cached
        /// for efficient per-frame length recompute in UpdateLastPosition.
        /// </summary>
        internal void SetEndpoints(Vector3 p0, Vector3 p1)
        {
            _core.positionCount = 2;
            _glow.positionCount = 2;
            SetAt(0, p0);
            SetAt(1, p1);
            _anchor = p0;
            SetTiling(Vector3.Distance(p0, p1));
        }

        /// <summary>
        /// Set positions from a slice of the corners array with Y offset applied.
        /// Used for the mid segment on recalculation.
        /// </summary>
        internal void SetFromCorners(Vector3[] src, int start, int count, float yOffset)
        {
            _core.positionCount = count;
            _glow.positionCount = count;
            float len = 0f;
            Vector3 prev = default;
            for (int i = 0; i < count; i++)
            {
                var p = src[start + i];
                p.y += yOffset;
                SetAt(i, p);
                if (i == 0)
                    _anchor = p;
                else
                    len += Vector3.Distance(prev, p);
                prev = p;
            }
            SetTiling(len);
        }

        /// <summary>
        /// Update position[last] (the dynamic endpoint) and recompute tiling
        /// using the cached anchor. For stub/tail this is always a two-point
        /// segment so the recompute is a single Distance call.
        /// </summary>
        internal void UpdateLastPosition(Vector3 pos)
        {
            int last = _core.positionCount - 1;
            if (last < 1)
                return;

            SetAt(last, pos);

            float len = 0f;
            Vector3 prev = _anchor;
            for (int i = 1; i <= last; i++)
            {
                var cur = _core.GetPosition(i);
                len += Vector3.Distance(prev, cur);
                prev = cur;
            }
            SetTiling(len);
        }

        /// <summary>Zero position count, hiding the segment.</summary>
        internal void Clear()
        {
            _core.positionCount = 0;
            _glow.positionCount = 0;
        }

        /// <summary>Enable or disable renderers. Never shows with fewer than 2 positions.</summary>
        internal void SetVisible(bool visible)
        {
            bool show = visible && _core.positionCount >= 2;
            _core.enabled = show;
            _glow.enabled = show;
        }

        private void SetAt(int i, Vector3 pos)
        {
            _core.SetPosition(i, pos);
            _glow.SetPosition(i, new Vector3(pos.x, pos.y - 0.01f, pos.z));
        }

        private void SetTiling(float len)
        {
            _coreMat.mainTextureScale = new Vector2(len * TileScale, 1f);
        }
    }

    // ── LineRenderer configuration ────────────────────────────────

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
        const float fadeZone = 0.10f; // smooth fade at dash edges

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
}
