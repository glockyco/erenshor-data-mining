using AdventureGuide.Config;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.Rendering;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using ImGuiNET;
using UnityEngine;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

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

    private readonly CompiledGuideModel _guide;
    private readonly QuestStateTracker _tracker;
    private readonly TrackerState _trackerState;
    private readonly NavigationSet _navSet;
    private readonly GuideWindow _guide_window;
    private readonly GuideConfig _config;
    private readonly NavigationTargetSelector _selector;
    private readonly TrackerSummaryResolver _summaryResolver;

    private bool _visible = true;
    private readonly Dictionary<string, EntryAnimation> _animations = new(
        StringComparer.OrdinalIgnoreCase
    );
    private readonly Dictionary<string, float> _fadingOut = new(StringComparer.OrdinalIgnoreCase);
    private readonly Dictionary<string, float> _completionTimers = new(
        StringComparer.OrdinalIgnoreCase
    );
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
        CompiledGuideModel guide,
        QuestStateTracker tracker,
        TrackerState trackerState,
        NavigationSet navSet,
        GuideWindow guideWindow,
        GuideConfig config,
        NavigationTargetSelector selector,
        TrackerSummaryResolver summaryResolver
    )
    {
        _guide = guide;
        _tracker = tracker;
        _trackerState = trackerState;
        _navSet = navSet;
        _guide_window = guideWindow;
        _config = config;
        _selector = selector;
        _summaryResolver = summaryResolver;

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

        if (
            _contentMax.Y > _contentMin.Y
            && GameWindowOverlap.ShouldSuppressTracker(
                _contentMin.X,
                _contentMin.Y,
                _contentMax.X,
                _contentMax.Y
            )
        )
            return;

        PruneAnimations();
        RebuildSortedListIfNeeded();

        if (_sorted.Count == 0 && _fadingOut.Count == 0)
            return;

        var cond = _config.LayoutResetRequested ? ImGuiCond.Always : ImGuiCond.FirstUseEver;
        var scale = _config.ResolvedUiScale;
        var display = ImGui.GetIO().DisplaySize;
        ImGui.SetNextWindowSize(
            new System.Numerics.Vector2(DefaultWidth * scale, DefaultHeight * scale),
            cond
        );
        ImGui.SetNextWindowPos(
            new System.Numerics.Vector2(40f, display.Y * 0.5f),
            cond,
            new System.Numerics.Vector2(0f, 0.5f)
        );

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
            uint tint = ImGuiColors.Rgba(0f, 0f, 0f, _config.TrackerBackgroundOpacity.Value);
            var bgDl = CimguiNative.igGetBackgroundDrawList_Nil();
            CimguiNative.ImDrawList_AddRectFilled(
                bgDl,
                new CimguiNative.Vec2(_contentMin.X, _contentMin.Y),
                new CimguiNative.Vec2(_contentMax.X, _contentMax.Y),
                tint,
                CompactTintRounding,
                DrawFlagsRoundCornersAll
            );
        }

        var flags =
            ImGuiWindowFlags.NoCollapse
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
            bool activeInteraction =
                ImGui.IsWindowFocused(ImGuiFocusedFlags.RootAndChildWindows)
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
        DrawNavAllButton();
        ImGui.SameLine(0, 6);
        DrawSortButton("Px", TrackerSortMode.Proximity, "Sort by proximity");
        ImGui.SameLine(0, 2);
        DrawSortButton("Lv", TrackerSortMode.Level, "Sort by level");
        ImGui.SameLine(0, 2);
        DrawSortButton("Az", TrackerSortMode.Alphabetical, "Sort alphabetically");
        ImGui.Separator();
    }

    private void DrawNavAllButton()
    {
        bool allActive = AllTrackedInNavSet();
        if (allActive)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton("NAV##tracker_nav_all"))
        {
            if (allActive)
                ClearTrackedFromNavSet();
            else
                AddAllTrackedToNavSet();
        }

        if (allActive)
            ImGui.PopStyleColor();

        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            ImGui.TextUnformatted(
                allActive
                    ? "Clear navigation for all tracked quests"
                    : "Navigate to all tracked quests"
            );
            ImGui.EndTooltip();
        }
    }

    private bool AllTrackedInNavSet()
    {
        if (_sorted.Count == 0)
            return false;
        for (int i = 0; i < _sorted.Count; i++)
        {
            var quest = _guide.GetQuestByDbName(_sorted[i]);
            if (quest != null && !_navSet.Contains(quest.Key))
                return false;
        }
        return true;
    }

    private void AddAllTrackedToNavSet()
    {
        var keys = new List<string>(_sorted.Count);
        for (int i = 0; i < _sorted.Count; i++)
        {
            var quest = _guide.GetQuestByDbName(_sorted[i]);
            if (quest != null)
                keys.Add(quest.Key);
        }
        _navSet.Load(keys);
    }

    private void ClearTrackedFromNavSet()
    {
        for (int i = 0; i < _sorted.Count; i++)
        {
            var quest = _guide.GetQuestByDbName(_sorted[i]);
            if (quest != null && _navSet.Contains(quest.Key))
                _navSet.Toggle(quest.Key);
        }
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
            var quest = _guide.GetQuestByDbName(dbName);
            if (quest != null)
                DrawQuestEntry(quest, dbName, i);
        }

        var contentBottom = ImGui.GetCursorScreenPos();
        var childPos = ImGui.GetWindowPos();
        float childWidth = ImGui.GetWindowWidth();
        float childHeight = ImGui.GetWindowHeight();
        float itemSpacing = ImGui.GetStyle().ItemSpacing.Y;
        float visibleBottom = childPos.Y + childHeight;
        float bottomY =
            contentBottom.Y <= visibleBottom
                ? contentBottom.Y - itemSpacing + CompactPadBottom
                : visibleBottom + CompactPadBottom;
        _contentMin = new System.Numerics.Vector2(
            childPos.X - CompactPadLeft,
            childPos.Y - CompactPadTop
        );
        _contentMax = new System.Numerics.Vector2(
            childPos.X + childWidth + CompactPadRight,
            bottomY
        );

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
                _guide_window.Show();
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

        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            if (!isActive)
                ImGui.TextUnformatted("Click to navigate\nShift+click to add");
            else if (_navSet.Count == 1)
                ImGui.TextUnformatted("Click to stop navigating\nShift+click to remove");
            else
                ImGui.TextUnformatted("Click to navigate here only\nShift+click to remove");
            ImGui.EndTooltip();
        }
    }

    private void DrawQuestNameAndLevel(Node quest, string dbName)
    {
        string label = quest.Level.HasValue
            ? $"{quest.Level.Value, 2}  {quest.DisplayName}"
            : $"    {quest.DisplayName}";

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.GetQuestColor(_tracker, dbName));
        if (ImGui.Selectable(label + "##name" + dbName))
        {
            _tracker.SelectQuest(dbName);
            _guide_window.Show();
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

        ResolvedQuestTarget? preferredTarget = _selector.TryGet(quest.Key, out var selected)
            ? selected.Target
            : null;
        var summaryEntry = _summaryResolver.Resolve(
            quest.Key,
            dbName,
            _tracker.CurrentZone,
            preferredTarget,
            _tracker
        );
        if (summaryEntry == null)
            return;

        TrackerSummary resolved = summaryEntry.Value;
        string distText = BuildDistanceText(quest.Key);
        string summary = resolved.PrimaryText;
        if (distText.Length > 0)
            summary += " " + distText;

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.TextWrapped(summary);
        if (!string.IsNullOrEmpty(resolved.SecondaryText))
            ImGui.TextWrapped(resolved.SecondaryText);
        if (!string.IsNullOrEmpty(resolved.RequiredForContext))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextDim);
            ImGui.TextWrapped(resolved.RequiredForContext);
            ImGui.PopStyleColor();
        }
        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);
    }

    private string BuildDistanceText(string questKey)
    {
        if (!_selector.TryGet(questKey, out var sel))
            return string.Empty;
        if (sel.IsSameZone && GameData.PlayerControl != null)
        {
            var p = GameData.PlayerControl.transform.position;
            float dx = sel.Target.X - p.x;
            float dy = sel.Target.Y - p.y;
            float dz = sel.Target.Z - p.z;
            float dist = UnityEngine.Mathf.Sqrt(dx * dx + dy * dy + dz * dz);
            return $"({(int)dist}m)";
        }
        if (!sel.IsSameZone)
        {
            return sel.HopCount == 1 ? "(1 hop)"
                : sel.HopCount > 1 ? $"({sel.HopCount} hops)"
                : string.Empty;
        }
        return string.Empty;
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

        bool proximityActive = _trackerState.SortMode == TrackerSortMode.Proximity;
        if (trackerDirty || stateDirty || sortModeChanged || proximityActive)
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
        _sorted.Sort(
            (a, b) =>
            {
                var na = _guide.GetQuestByDbName(a);
                var nb = _guide.GetQuestByDbName(b);
                if (na == null || nb == null)
                    return 0;

                return _trackerState.SortMode switch
                {
                    TrackerSortMode.Proximity => CompareByProximity(na, nb),
                    TrackerSortMode.Level => CompareByLevel(na, nb),
                    TrackerSortMode.Alphabetical => string.Compare(
                        na.DisplayName,
                        nb.DisplayName,
                        StringComparison.OrdinalIgnoreCase
                    ),
                    _ => 0,
                };
            }
        );
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
        bool aInZone = _selector.TryGet(a.Key, out var selA) && selA.IsSameZone;
        bool bInZone = _selector.TryGet(b.Key, out var selB) && selB.IsSameZone;

        if (aInZone && !bInZone)
            return -1;
        if (!aInZone && bInZone)
            return 1;

        if (aInZone) // both in zone
        {
            float distA = 0f,
                distB = 0f;
            if (GameData.PlayerControl != null)
            {
                var p = GameData.PlayerControl.transform.position;
                float dxA = selA.Target.X - p.x,
                    dyA = selA.Target.Y - p.y,
                    dzA = selA.Target.Z - p.z;
                float dxB = selB.Target.X - p.x,
                    dyB = selB.Target.Y - p.y,
                    dzB = selB.Target.Z - p.z;
                distA = dxA * dxA + dyA * dyA + dzA * dzA; // squared: monotone, valid for comparison
                distB = dxB * dxB + dyB * dyB + dzB * dzB;
            }
            int cmp = distA.CompareTo(distB);
            return cmp != 0
                ? cmp
                : string.Compare(a.DisplayName, b.DisplayName, StringComparison.OrdinalIgnoreCase);
        }

        // Both cross-zone: compare by hop count, then level
        int hopCmp = selA.HopCount.CompareTo(selB.HopCount);
        return hopCmp != 0 ? hopCmp : CompareByLevel(a, b);
    }

    private EntryAnimation GetOrDefaultAnim(string dbName) =>
        _animations.TryGetValue(dbName, out var anim) ? anim : default;

    private struct EntryAnimation
    {
        public float AddedAt;
        public float CompletedAt;
    }
}
