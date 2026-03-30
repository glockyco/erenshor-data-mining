using AdventureGuide.Rendering;
using AdventureGuide.Frontier;
using AdventureGuide.Config;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using ImGuiNET;
using UnityEngine;

namespace AdventureGuide.UI;

/// <summary>
/// Compact always-visible quest tracker overlay.
/// Renders tracked quests as a projection of shared quest resolutions rather than
/// rebuilding frontier semantics locally.
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
    private readonly TrackerState _trackerState;
    private readonly NavigationSet _navSet;
    private readonly GuideWindow _guide;
    private readonly GuideConfig _config;
    private readonly ZoneRouter _router;
    private readonly QuestResolutionService _resolution;

    private bool _visible = true;
    private readonly Dictionary<string, EntryAnimation> _animations = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, float> _fadingOut = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, float> _completionTimers = new(StringComparer.OrdinalIgnoreCase);
    private readonly List<string> _sorted = new();
    private int _lastStateVersion = -1;
    private TrackerSortMode _lastSortMode;
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
        TrackerState trackerState,
        NavigationSet navSet,
        GuideWindow guide,
        GuideConfig config,
        ZoneRouter router,
        QuestResolutionService resolution)
    {
        _graph = graph;
        _tracker = tracker;
        _trackerState = trackerState;
        _navSet = navSet;
        _guide = guide;
        _config = config;
        _router = router;
        _resolution = resolution;

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

    public void Draw()
    {
        if (!_visible || !_trackerState.Enabled)
            return;

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

        if (_compact && _contentMax.Y > _contentMin.Y)
        {
            uint tint = Theme.Rgba(0f, 0f, 0f, _config.TrackerBackgroundOpacity.Value);
            var bgDl = CimguiNative.igGetBackgroundDrawList_Nil();
            CimguiNative.ImDrawList_AddRectFilled(
                bgDl,
                new CimguiNative.Vec2(_contentMin.X, _contentMin.Y),
                new CimguiNative.Vec2(_contentMax.X, _contentMax.Y),
                tint,
                CompactTintRounding,
                DrawFlagsRoundCornersAll);
        }

        var flags = ImGuiWindowFlags.NoCollapse
            | ImGuiWindowFlags.NoFocusOnAppearing
            | ImGuiWindowFlags.NoNav
            | ImGuiWindowFlags.NoBringToFrontOnFocus;
        if (_compact)
            flags |= ImGuiWindowFlags.NoResize | ImGuiWindowFlags.NoScrollbar;

        bool beginOpen = _compact
            ? ImGui.Begin("###Tracker", flags)
            : ImGui.Begin("Quest Tracker###Tracker", ref _visible, flags);

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

    private void DrawQuestList()
    {
        ImGui.BeginChild("##TrackerScroll", System.Numerics.Vector2.Zero, false);

        var contentTop = ImGui.GetCursorScreenPos();
        for (int i = 0; i < _sorted.Count; i++)
        {
            var dbName = _sorted[i];
            var quest = _graph.GetQuestByDbName(dbName);
            if (quest != null)
                DrawQuestEntry(quest, dbName, i);
        }

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

        if (!isFadingOut && !_trackerState.IsTracked(dbName))
            return;

        float entryAlpha = 1f;
        if (isFadingOut)
        {
            float elapsed = now - fadeStart;
            entryAlpha = Mathf.Clamp01(1f - elapsed / FadeOutDuration);
            if (entryAlpha <= 0f)
                return;
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

        DrawNavButton(quest);
        ImGui.SameLine();
        DrawQuestNameAndLevel(quest, dbName);
        DrawResolutionSummary(quest);

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

    private void DrawResolutionSummary(Node quest)
    {
        string? dbName = quest.DbName;
        if (dbName != null && _tracker.IsCompleted(dbName))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestCompleted);
            ImGui.Text("  Completed");
            ImGui.PopStyleColor();
            return;
        }

        var resolution = _resolution.ResolveQuest(quest.Key);
        string summary = resolution.TrackerSummary.PrimaryText;
        string distText = ComputeDistanceText(resolution);
        if (distText.Length > 0)
            summary += " " + distText;

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextWrapped(summary);
        if (!string.IsNullOrEmpty(resolution.TrackerSummary.SecondaryText))
            ImGui.TextWrapped(resolution.TrackerSummary.SecondaryText);
        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);
    }

    private string ComputeDistanceText(QuestResolution resolution)
    {
        if (resolution.Targets.Count == 0 || GameData.PlayerControl == null)
            return "";

        var playerPos = GameData.PlayerControl.transform.position;
        float minDistance = float.MaxValue;
        for (int i = 0; i < resolution.Targets.Count; i++)
        {
            var target = resolution.Targets[i];
            if (!string.Equals(target.Scene, _tracker.CurrentZone, StringComparison.OrdinalIgnoreCase))
                continue;

            float distance = Vector3.Distance(playerPos, target.Position);
            if (distance < minDistance)
                minDistance = distance;
        }

        if (minDistance < float.MaxValue)
            return $"({(int)minDistance}m)";

        int bestHops = GetBestHopCount(resolution);
        if (bestHops > 0)
            return bestHops == 1 ? "(1 hop)" : $"({bestHops} hops)";

        return "";
    }

    private float GetMinFrontierDistance(string questKey)
    {
        var resolution = _resolution.ResolveQuest(questKey);
        if (resolution.Targets.Count == 0 || GameData.PlayerControl == null)
            return float.MaxValue;

        var playerPos = GameData.PlayerControl.transform.position;
        float minDistance = float.MaxValue;
        for (int i = 0; i < resolution.Targets.Count; i++)
        {
            var target = resolution.Targets[i];
            if (!string.Equals(target.Scene, _tracker.CurrentZone, StringComparison.OrdinalIgnoreCase))
                continue;

            float distance = Vector3.Distance(playerPos, target.Position);
            if (distance < minDistance)
                minDistance = distance;
        }

        return minDistance;
    }

    private int GetBestHopCount(QuestResolution resolution)
    {
        int bestHops = int.MaxValue;
        for (int i = 0; i < resolution.Targets.Count; i++)
        {
            var target = resolution.Targets[i];
            if (string.IsNullOrEmpty(target.Scene))
                continue;

            var route = _router.FindRoute(_tracker.CurrentZone, target.Scene!);
            if (route == null)
                continue;

            int hops = route.Path.Count - 1;
            if (hops < bestHops)
                bestHops = hops;
        }

        return bestHops == int.MaxValue ? -1 : bestHops;
    }

    private void PruneAnimations()
    {
        float now = Time.realtimeSinceStartup;

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

    private void RebuildSortedListIfNeeded()
    {
        bool trackerDirty = _trackerState.IsDirty;
        bool stateDirty = _tracker.Version != _lastStateVersion;
        bool sortModeChanged = _trackerState.SortMode != _lastSortMode;

        if (trackerDirty || stateDirty || sortModeChanged)
        {
            if (stateDirty)
                _lastStateVersion = _tracker.Version;
            RebuildSortedList();
        }
    }

    private void RebuildSortedList()
    {
        _sorted.Clear();
        _sorted.AddRange(_trackerState.TrackedQuests);

        foreach (var dbName in _fadingOut.Keys)
        {
            if (!_sorted.Contains(dbName))
                _sorted.Add(dbName);
        }

        _lastSortMode = _trackerState.SortMode;
        _sorted.Sort((a, b) =>
        {
            var na = _graph.GetQuestByDbName(a);
            var nb = _graph.GetQuestByDbName(b);
            if (na == null || nb == null)
                return 0;

            return _trackerState.SortMode switch
            {
                TrackerSortMode.Proximity => CompareByProximity(na, nb),
                TrackerSortMode.Level => CompareByLevel(na, nb),
                TrackerSortMode.Alphabetical => string.Compare(
                    na.DisplayName,
                    nb.DisplayName,
                    StringComparison.OrdinalIgnoreCase),
                _ => 0,
            };
        });
    }

    private static int CompareByLevel(Node a, Node b)
    {
        int la = a.Level ?? int.MaxValue;
        int lb = b.Level ?? int.MaxValue;
        int cmp = la.CompareTo(lb);
        return cmp != 0
            ? cmp
            : string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
    }

    private int CompareByProximity(Node a, Node b)
    {
        float distA = GetMinFrontierDistance(a.Key);
        float distB = GetMinFrontierDistance(b.Key);

        bool aInZone = distA < float.MaxValue;
        bool bInZone = distB < float.MaxValue;
        if (aInZone && !bInZone)
            return -1;
        if (!aInZone && bInZone)
            return 1;

        if (aInZone && bInZone)
        {
            int cmp = distA.CompareTo(distB);
            return cmp != 0
                ? cmp
                : string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
        }

        int hopsA = GetBestHopCount(_resolution.ResolveQuest(a.Key));
        int hopsB = GetBestHopCount(_resolution.ResolveQuest(b.Key));
        int hopCmp = hopsA.CompareTo(hopsB);
        return hopCmp != 0
            ? hopCmp
            : CompareByLevel(a, b);
    }

    private EntryAnimation GetOrDefaultAnim(string dbName) =>
        _animations.TryGetValue(dbName, out var anim) ? anim : default;

    private struct EntryAnimation
    {
        public float AddedAt;
        public float CompletedAt;
    }
}
