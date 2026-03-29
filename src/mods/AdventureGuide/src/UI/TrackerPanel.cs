using AdventureGuide.Config;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Rendering;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using AdventureGuide.Views;
using ImGuiNET;
using UnityEngine;

namespace AdventureGuide.UI;

/// <summary>
/// Compact always-visible quest tracker overlay. Shows tracked quests with
/// their frontier summary (what to do next) and NAV buttons.
///
/// Features ported from the original TrackerWindow, adapted to the entity
/// graph model:
/// - Compact mode: transparent backdrop when not hovered, full window on hover
/// - Animations: fade-in on track, fade-out on untrack, completion flash
/// - Sort modes: proximity, level, alphabetical
/// - Game window overlap suppression
/// - Auto-untrack on quest completion
/// - Right-click context menu (untrack, open in guide)
/// </summary>
public sealed class TrackerPanel
{
    private const float DefaultWidth = 340f;
    private const float DefaultHeight = 260f;
    private const float FadeInDuration = 0.3f;
    private const float FadeOutDuration = 0.3f;
    private const float CompletionFlashDuration = 1.5f;
    private const float CompletionLingerDuration = 2.0f;
    private const float CompactTintRounding = 8f;
    private const float CompactPadTop = 10f;
    private const float CompactPadBottom = 6f;
    private const float CompactPadLeft = 8f;
    private const float CompactPadRight = 6f;
    private const int DrawFlagsRoundCornersAll = 240;

    private readonly EntityGraph _graph;
    private readonly QuestStateTracker _tracker;
    private readonly GameState _state;
    private readonly TrackerState _trackerState;
    private readonly QuestViewBuilder _viewBuilder;
    private readonly NavigationSet _navSet;
    private readonly GuideWindow _guide;
    private readonly GuideConfig _config;
    private readonly ZoneRouter _router;
    private readonly ViewNodePositionCollector _viewPositions;

    private bool _visible = true;

    // Animation state
    private readonly Dictionary<string, EntryAnimation> _animations = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, float> _fadingOut = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, float> _completionTimers = new(StringComparer.OrdinalIgnoreCase);

    // Sorted working copy — includes both tracked and fading-out entries
    private readonly List<string> _sorted = new();
    private int _lastStateVersion = -1;
    private TrackerSortMode _lastSortMode;

    // Frontier cache — avoids rebuilding view trees every frame.
    // Stores summary text and frontier positions for distance computation.
    private readonly Dictionary<string, CachedFrontier> _frontierCache = new(StringComparer.OrdinalIgnoreCase);
    private int _frontierCacheVersion = -1;

    // Compact mode state
    private bool _compact = true;
    private System.Numerics.Vector2 _contentMin;
    private System.Numerics.Vector2 _contentMax;

    public bool Visible => _visible;
    public void Toggle() => _visible = !_visible;
    public void Show() => _visible = true;
    public void Hide() => _visible = false;

    public TrackerPanel(
        EntityGraph graph,
        QuestStateTracker tracker,
        GameState state,
        TrackerState trackerState,
        QuestViewBuilder viewBuilder,
        NavigationSet navSet,
        GuideWindow guide,
        GuideConfig config,
        ZoneRouter router,
        ViewNodePositionCollector viewPositions)
    {
        _graph = graph;
        _tracker = tracker;
        _state = state;
        _trackerState = trackerState;
        _viewBuilder = viewBuilder;
        _navSet = navSet;
        _guide = guide;
        _config = config;
        _router = router;
        _viewPositions = viewPositions;

        _trackerState.Tracked += OnQuestTracked;
        _trackerState.Untracked += OnQuestUntracked;
        _trackerState.QuestCompleted += OnQuestCompleted;
    }

    public void Dispose()
    {
        _trackerState.Tracked -= OnQuestTracked;
        _trackerState.Untracked -= OnQuestUntracked;
        _trackerState.QuestCompleted -= OnQuestCompleted;
    }

    // ── Event handlers ───────────────────────────────────────────────

    private void OnQuestTracked(string dbName)
    {
        _animations[dbName] = new EntryAnimation { AddedAt = Time.realtimeSinceStartup };
        _fadingOut.Remove(dbName);
        _visible = true;
    }

    private void OnQuestUntracked(string dbName)
    {
        _fadingOut[dbName] = Time.realtimeSinceStartup;
        _completionTimers.Remove(dbName);
    }

    private void OnQuestCompleted(string dbName)
    {
        var anim = GetOrDefaultAnim(dbName);
        anim.CompletedAt = Time.realtimeSinceStartup;
        _animations[dbName] = anim;
        _completionTimers[dbName] = Time.realtimeSinceStartup;
    }

    // ── Draw ─────────────────────────────────────────────────────────

    public void Draw()
    {
        if (!_visible || !_trackerState.Enabled) return;

        // Hide when game UI overlaps us
        if (_contentMax.Y > _contentMin.Y
            && GameWindowOverlap.ShouldSuppressTracker(
                _contentMin.X, _contentMin.Y, _contentMax.X, _contentMax.Y))
            return;

        PruneAnimations();
        RebuildSortedListIfNeeded();

        if (_sorted.Count == 0 && _fadingOut.Count == 0)
            return;

        var cond = _config.LayoutResetRequested ? ImGuiCond.Always : ImGuiCond.FirstUseEver;
        var scale = _config.ResolvedUiScale;
        var display = ImGui.GetIO().DisplaySize;
        ImGui.SetNextWindowSize(new System.Numerics.Vector2(DefaultWidth * scale, DefaultHeight * scale), cond);
        ImGui.SetNextWindowPos(
            new System.Numerics.Vector2(40f, display.Y * 0.5f), cond,
            new System.Numerics.Vector2(0f, 0.5f));

        int extraColors = 0;
        Theme.PushWindowStyle();
        if (_compact)
        {
            ImGui.PushStyleColor(ImGuiCol.WindowBg, 0u);
            ImGui.PushStyleColor(ImGuiCol.ChildBg, 0u);
            ImGui.PushStyleColor(ImGuiCol.Border, 0u);
            ImGui.PushStyleColor(ImGuiCol.TitleBg, 0u);
            ImGui.PushStyleColor(ImGuiCol.TitleBgActive, 0u);
            ImGui.PushStyleColor(ImGuiCol.TitleBgCollapsed, 0u);
            ImGui.PushStyleColor(ImGuiCol.Button, 0u);
            ImGui.PushStyleColor(ImGuiCol.FrameBg, 0u);
            extraColors = 8;
        }

        // Draw fitted tint backdrop using last frame's content bounds
        if (_compact && _contentMax.Y > _contentMin.Y)
        {
            uint tint = Theme.Rgba(0f, 0f, 0f, _config.TrackerBackgroundOpacity.Value);
            var bgDl = CimguiNative.igGetBackgroundDrawList_Nil();
            CimguiNative.ImDrawList_AddRectFilled(
                bgDl,
                new CimguiNative.Vec2(_contentMin.X, _contentMin.Y),
                new CimguiNative.Vec2(_contentMax.X, _contentMax.Y),
                tint, CompactTintRounding, DrawFlagsRoundCornersAll);
        }

        var flags = ImGuiWindowFlags.NoCollapse
            | ImGuiWindowFlags.NoFocusOnAppearing
            | ImGuiWindowFlags.NoNav
            | ImGuiWindowFlags.NoBringToFrontOnFocus;
        if (_compact)
            flags |= ImGuiWindowFlags.NoResize | ImGuiWindowFlags.NoScrollbar;

        bool beginOpen;
        if (_compact)
            beginOpen = ImGui.Begin("###Tracker", flags);
        else
            beginOpen = ImGui.Begin("Quest Tracker###Tracker", ref _visible, flags);

        if (beginOpen)
        {
            if (_compact)
                ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0f);
            DrawHeaderBar();
            if (_compact)
                ImGui.PopStyleVar();

            DrawQuestList();

            bool hovered = ImGui.IsWindowHovered(ImGuiHoveredFlags.RootAndChildWindows);
            bool activeInteraction = ImGui.IsWindowFocused(ImGuiFocusedFlags.RootAndChildWindows)
                && ImGui.IsMouseDown(ImGuiMouseButton.Left);
            _compact = !hovered && !activeInteraction;

            if (_compact && ImGui.IsWindowFocused(ImGuiFocusedFlags.RootAndChildWindows))
                ImGui.SetWindowFocus(null);
        }

        Theme.ClampWindowPosition();

        ImGui.End();
        if (extraColors > 0)
            ImGui.PopStyleColor(extraColors);
        Theme.PopWindowStyle();
    }

    // ── Header bar ───────────────────────────────────────────────────

    private void DrawHeaderBar()
    {
        DrawSortButton("Px", TrackerSortMode.Proximity, "Sort by proximity");
        ImGui.SameLine(0, 2);
        DrawSortButton("Lv", TrackerSortMode.Level, "Sort by level");
        ImGui.SameLine(0, 2);
        DrawSortButton("Az", TrackerSortMode.Alphabetical, "Sort alphabetically");

        ImGui.Separator();
    }

    private void DrawSortButton(string label, TrackerSortMode mode, string tooltip)
    {
        bool active = _trackerState.SortMode == mode;
        if (active)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton(label + "##tsort"))
        {
            _trackerState.SortMode = mode;
            _lastSortMode = mode;
            RebuildSortedList();
        }

        if (active)
            ImGui.PopStyleColor();

        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            ImGui.TextUnformatted(tooltip);
            ImGui.EndTooltip();
        }
    }

    // ── Quest list ───────────────────────────────────────────────────

    private void DrawQuestList()
    {
        ImGui.BeginChild("##TrackerScroll", System.Numerics.Vector2.Zero, false);

        var contentTop = ImGui.GetCursorScreenPos();

        for (int i = 0; i < _sorted.Count; i++)
        {
            var dbName = _sorted[i];
            var quest = _graph.GetQuestByDbName(dbName);
            if (quest == null) continue;

            DrawQuestEntry(quest, dbName, i);
        }

        // Record bounds for backdrop
        var contentBottom = ImGui.GetCursorScreenPos();
        var childPos = ImGui.GetWindowPos();
        float childWidth = ImGui.GetWindowWidth();
        float childHeight = ImGui.GetWindowHeight();
        float itemSpacing = ImGui.GetStyle().ItemSpacing.Y;
        float visibleBottom = childPos.Y + childHeight;
        float bottomY = contentBottom.Y <= visibleBottom
            ? contentBottom.Y - itemSpacing + CompactPadBottom
            : visibleBottom + CompactPadBottom;
        _contentMin = new System.Numerics.Vector2(childPos.X - CompactPadLeft, childPos.Y - CompactPadTop);
        _contentMax = new System.Numerics.Vector2(childPos.X + childWidth + CompactPadRight, bottomY);

        ImGui.EndChild();
    }

    private void DrawQuestEntry(Node quest, string dbName, int index)
    {
        var anim = GetOrDefaultAnim(dbName);
        float now = Time.realtimeSinceStartup;
        bool isFadingOut = _fadingOut.TryGetValue(dbName, out float fadeStart);

        if (!isFadingOut && !_trackerState.IsTracked(dbName)) return;

        float entryAlpha = 1f;
        if (isFadingOut)
        {
            float elapsed = now - fadeStart;
            entryAlpha = Mathf.Clamp01(1f - elapsed / FadeOutDuration);
            if (entryAlpha <= 0f) return;
        }
        else if (anim.AddedAt > 0)
        {
            float elapsed = now - anim.AddedAt;
            if (elapsed < FadeInDuration)
                entryAlpha = elapsed / FadeInDuration;
        }

        ImGui.PushID(index);

        if (entryAlpha < 1f)
            ImGui.PushStyleVar(ImGuiStyleVar.Alpha, entryAlpha);

        bool tinted = false;
        if (anim.CompletedAt > 0 && now - anim.CompletedAt < CompletionFlashDuration)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Success);
            tinted = true;
        }

        // NAV button
        DrawNavButton(quest);
        ImGui.SameLine();

        // Quest name with level prefix
        DrawQuestNameAndLevel(quest, dbName);

        // Frontier summary: what to do next
        DrawFrontierSummary(quest);

        // Right-click context menu
        if (ImGui.BeginPopupContextItem($"##ctx{dbName}"))
        {
            if (ImGui.Selectable("Untrack"))
                _trackerState.Untrack(dbName);
            if (ImGui.Selectable("Open in Guide"))
            {
                _tracker.SelectQuest(dbName);
                _guide.Show();
            }
            ImGui.EndPopup();
        }

        ImGui.Spacing();

        if (tinted)
            ImGui.PopStyleColor();
        if (entryAlpha < 1f)
            ImGui.PopStyleVar();

        ImGui.PopID();
    }

    // ── NAV button ───────────────────────────────────────────────────

    private void DrawNavButton(Node quest)
    {
        bool isActive = _navSet.Contains(quest.Key);
        if (isActive)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton($"NAV###{quest.Key}_tracker"))
        {
            if (ImGui.GetIO().KeyShift)
                _navSet.Toggle(quest.Key);
            else if (isActive && _navSet.Count == 1)
                _navSet.Clear();
            else
                _navSet.Override(quest.Key);
        }

        if (isActive)
            ImGui.PopStyleColor();
    }

    // ── Quest name + level ───────────────────────────────────────────

    private void DrawQuestNameAndLevel(Node quest, string dbName)
    {
        string label = quest.Level.HasValue
            ? $"{quest.Level.Value,2}  {quest.DisplayName}"
            : $"    {quest.DisplayName}";

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.GetQuestColor(_tracker, dbName));
        if (ImGui.Selectable(label + "##name" + dbName))
        {
            _tracker.SelectQuest(dbName);
            _guide.Show();
        }
        ImGui.PopStyleColor();
    }

    // ── Frontier summary ─────────────────────────────────────────────

    private void DrawFrontierSummary(Node quest)
    {
        string? dbName = quest.DbName;
        if (dbName != null && _tracker.IsCompleted(dbName))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestCompleted);
            ImGui.Text("  Completed");
            ImGui.PopStyleColor();
            return;
        }

        var frontier = GetCachedFrontier(quest.Key);
        string summary = frontier.Summary;

        // Append distance annotation
        string distText = ComputeDistanceText(frontier);
        if (distText.Length > 0)
            summary += $" {distText}";

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextWrapped(summary);
        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);
    }

    private CachedFrontier GetCachedFrontier(string questKey)
    {
        // Invalidate cache when game state changes (quest/inventory updates)
        if (_tracker.Version != _frontierCacheVersion)
        {
            _frontierCache.Clear();
            _frontierCacheVersion = _tracker.Version;
        }

        if (_frontierCache.TryGetValue(questKey, out var cached))
            return cached;

        var result = ComputeFrontierInfo(questKey);
        _frontierCache[questKey] = result;
        return result;
    }

    private CachedFrontier ComputeFrontierInfo(string questKey)
    {
        var root = _viewBuilder.Build(questKey);
        if (root == null)
            return new CachedFrontier("Unknown", System.Array.Empty<FrontierPosition>());

        var frontier = FrontierComputer.ComputeFrontier(root, _state);
        if (frontier.Count == 0)
            return new CachedFrontier("Ready to turn in", System.Array.Empty<FrontierPosition>());

        // Build summary from first frontier ViewNode using shared formatter.
        // The ViewNode carries edge type/keyword/quantity for action text.
        string summary = ActionTextFormatter.FormatSummary(frontier[0], _tracker);
        if (frontier.Count > 1)
            summary += $" (+{frontier.Count - 1} more)";

        // Collect positions for distance computation from the same pruned
        // frontier nodes the quest view renders and navigation uses.

        var positions = new List<FrontierPosition>();
        for (int i = 0; i < frontier.Count; i++)
            CollectFrontierPositions(frontier[i], positions);

        // Prepend cross-zone prefix when all frontier is outside current scene
        if (positions.Count > 0)
        {
            string currentScene = _tracker.CurrentZone;
            bool anyInZone = false;
            foreach (var p in positions)
            {
                if (string.Equals(p.Scene, currentScene, StringComparison.OrdinalIgnoreCase))
                {
                    anyInZone = true;
                    break;
                }
            }
            if (!anyInZone)
            {
                // Find zone name from first frontier node with one
                for (int i = 0; i < frontier.Count; i++)
                {
                    if (frontier[i].Node.Zone != null)
                    {
                        summary = $"In {frontier[i].Node.Zone}: {summary}";
                        break;
                    }
                }
            }
        }

        return new CachedFrontier(
            summary,
            positions.Count > 0 ? positions.ToArray() : System.Array.Empty<FrontierPosition>());
    }

    /// <summary>
    /// Collect world positions for a frontier node from its pruned view tree.
    /// This keeps tracker distance computation consistent with navigation and
    /// the rendered dependency tree.
    /// </summary>
    private void CollectFrontierPositions(ViewNode node, List<FrontierPosition> positions)
    {
        var resolved = new List<ResolvedPosition>();
        _viewPositions.Collect(node, resolved);
        for (int i = 0; i < resolved.Count; i++)
        {
            var rp = resolved[i];
            positions.Add(new FrontierPosition(
                rp.Position.x, rp.Position.y, rp.Position.z, rp.Scene ?? ""));
        }
    }

    /// <summary>
    /// Compute distance text for display: "(42m)" for same-zone,
    /// "({n} hops)" for cross-zone.
    /// </summary>
    private string ComputeDistanceText(CachedFrontier frontier)
    {
        if (frontier.Positions.Length == 0)
            return "";

        string currentScene = _tracker.CurrentZone;
        var playerCtrl = GameData.PlayerControl;
        if (playerCtrl == null) return "";
        var playerPos = playerCtrl.transform.position;

        // Check for same-zone frontier nodes
        float minDist = float.MaxValue;
        foreach (var p in frontier.Positions)
        {
            if (!string.Equals(p.Scene, currentScene, StringComparison.OrdinalIgnoreCase))
                continue;
            float dist = Vector3.Distance(playerPos, new Vector3(p.X, p.Y, p.Z));
            if (dist < minDist) minDist = dist;
        }

        if (minDist < float.MaxValue)
            return $"({(int)minDist}m)";

        // All frontier nodes are cross-zone
        string? bestZone = null;
        int bestHops = int.MaxValue;
        foreach (var p in frontier.Positions)
        {
            if (string.IsNullOrEmpty(p.Scene)) continue;
            var route = _router.FindRoute(currentScene, p.Scene);
            if (route == null) continue;
            int hops = route.Path.Count - 1;
            if (hops < bestHops)
            {
                bestHops = hops;
                bestZone = p.Scene;
            }
        }

        if (bestZone != null && bestHops > 0)
        {
            string hopText = bestHops == 1 ? "1 hop" : $"{bestHops} hops";
            return $"({hopText})";
        }

        return "";
    }

    /// <summary>
    /// Get minimum distance from player to any same-zone frontier node.
    /// Returns float.MaxValue if no frontier nodes are in the current zone.
    /// </summary>
    private float GetMinFrontierDistance(string questKey)
    {
        var frontier = GetCachedFrontier(questKey);
        if (frontier.Positions.Length == 0)
            return float.MaxValue;

        string currentScene = _tracker.CurrentZone;
        var playerCtrl = GameData.PlayerControl;
        if (playerCtrl == null) return float.MaxValue;
        var playerPos = playerCtrl.transform.position;

        float minDist = float.MaxValue;
        foreach (var p in frontier.Positions)
        {
            if (!string.Equals(p.Scene, currentScene, StringComparison.OrdinalIgnoreCase))
                continue;
            float dist = Vector3.Distance(playerPos, new Vector3(p.X, p.Y, p.Z));
            if (dist < minDist) minDist = dist;
        }

        return minDist;
    }

    // ── Animation management ─────────────────────────────────────────

    private void PruneAnimations()
    {
        float now = Time.realtimeSinceStartup;

        // Auto-untrack completed quests after flash
        var toUntrack = new List<string>();
        foreach (var (dbName, startTime) in _completionTimers)
        {
            if (now - startTime > CompletionLingerDuration)
                toUntrack.Add(dbName);
        }
        foreach (var dbName in toUntrack)
        {
            _completionTimers.Remove(dbName);
            _trackerState.Untrack(dbName);
        }

        // Remove expired fade-outs
        var expiredFades = new List<string>();
        foreach (var (dbName, startTime) in _fadingOut)
        {
            if (now - startTime > FadeOutDuration)
                expiredFades.Add(dbName);
        }
        foreach (var dbName in expiredFades)
        {
            _fadingOut.Remove(dbName);
            _animations.Remove(dbName);
        }
    }

    // ── Sort management ──────────────────────────────────────────────

    private void RebuildSortedListIfNeeded()
    {
        bool trackerDirty = _trackerState.IsDirty;
        bool stateDirty = _tracker.Version != _lastStateVersion;
        bool sortModeChanged = _trackerState.SortMode != _lastSortMode;

        if (trackerDirty || stateDirty || sortModeChanged)
        {
            if (stateDirty) _lastStateVersion = _tracker.Version;
            RebuildSortedList();
        }
    }

    private void RebuildSortedList()
    {
        _sorted.Clear();
        _sorted.AddRange(_trackerState.TrackedQuests);

        // Append fading-out entries so they fade in place
        foreach (var dbName in _fadingOut.Keys)
        {
            if (!_sorted.Contains(dbName))
                _sorted.Add(dbName);
        }

        _lastSortMode = _trackerState.SortMode;

        // Sort based on mode
        _sorted.Sort((a, b) =>
        {
            var na = _graph.GetQuestByDbName(a);
            var nb = _graph.GetQuestByDbName(b);
            if (na == null || nb == null) return 0;

            return _trackerState.SortMode switch
            {
                TrackerSortMode.Proximity => CompareByProximity(na, nb),
                TrackerSortMode.Level => CompareByLevel(na, nb),
                TrackerSortMode.Alphabetical => string.Compare(
                    na.DisplayName, nb.DisplayName, StringComparison.OrdinalIgnoreCase),
                _ => 0,
            };
        });
    }

    private static int CompareByLevel(Node a, Node b)
    {
        int la = a.Level ?? int.MaxValue;
        int lb = b.Level ?? int.MaxValue;
        int cmp = la.CompareTo(lb);
        return cmp != 0 ? cmp : string.Compare(
            a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>
    /// Compare quests by proximity: same-zone quests first (sorted by distance),
    /// then cross-zone quests (sorted by hop count). Tie-break alphabetically.
    /// </summary>
    private int CompareByProximity(Node a, Node b)
    {
        float distA = GetMinFrontierDistance(a.Key);
        float distB = GetMinFrontierDistance(b.Key);

        bool aInZone = distA < float.MaxValue;
        bool bInZone = distB < float.MaxValue;

        // Same-zone quests sort before cross-zone
        if (aInZone && !bInZone) return -1;
        if (!aInZone && bInZone) return 1;

        // Both in zone: sort by distance
        if (aInZone && bInZone)
        {
            int cmp = distA.CompareTo(distB);
            return cmp != 0 ? cmp : string.Compare(
                a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
        }

        // Both cross-zone: compare by level as proxy for closeness
        return CompareByLevel(a, b);
    }

    // ── Helpers ──────────────────────────────────────────────────────

    private EntryAnimation GetOrDefaultAnim(string dbName) =>
        _animations.TryGetValue(dbName, out var anim) ? anim : default;

    private struct EntryAnimation
    {
        public float AddedAt;
        public float CompletedAt;
    }
}


/// <summary>Cached frontier computation result for a quest.</summary>
internal readonly struct CachedFrontier
{
    public readonly string Summary;
    public readonly FrontierPosition[] Positions;

    public CachedFrontier(string summary, FrontierPosition[] positions)
    {
        Summary = summary;
        Positions = positions;
    }
}

/// <summary>World position of a frontier node for distance computation.</summary>
internal readonly struct FrontierPosition
{
    public readonly float X, Y, Z;
    public readonly string Scene;

    public FrontierPosition(float x, float y, float z, string scene)
    {
        X = x;
        Y = y;
        Z = z;
        Scene = scene;
    }
}