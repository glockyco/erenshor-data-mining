using System.Numerics;
using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.Rendering;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Compact always-visible quest tracker overlay rendered via Dear ImGui.
/// Shows tracked quest objectives with navigation integration, sorting,
/// and state change animations.
///
/// Owns all animation state. TrackerState is pure logical state — this
/// class subscribes to its events and manages visual effects (fade-in,
/// fade-out, completion flash, step advance highlight).
/// </summary>
public sealed class TrackerWindow
{
    private const float DefaultWidth = 340f;
    private const float DefaultHeight = 260f;
    private const float FadeInDuration = 0.3f;
    private const float FadeOutDuration = 0.3f;
    private const float CompletionFlashDuration = 1.5f;
    private const float CompletionLingerDuration = 2.0f;
    private const float StepAdvanceDuration = 0.8f;
    private const float CompactTintRounding = 8f;
    private const float CompactPadTop = 10f;
    private const float CompactPadBottom = 6f;
    private const float CompactPadLeft = 8f;
    private const float CompactPadRight = 6f;
    private const int DrawFlagsRoundCornersAll = 240;

    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly NavigationController _nav;
    private readonly TrackerState _tracker;
    private readonly GuideWindow _guide;
    private readonly GuideConfig _config;
    private bool _visible = true;

    // Animation state — owned by this window, not TrackerState
    private readonly Dictionary<string, EntryAnimation> _animations = new(System.StringComparer.OrdinalIgnoreCase);

    // Entries being faded out (already removed from TrackerState)
    private readonly Dictionary<string, float> _fadingOut = new(System.StringComparer.OrdinalIgnoreCase);

    // Completed quests pending auto-untrack after flash duration
    private readonly Dictionary<string, float> _completionTimers = new(System.StringComparer.OrdinalIgnoreCase);

    // Sorted working copy — includes both tracked and fading-out entries
    private readonly List<string> _sorted = new();
    private readonly Dictionary<string, StepDistance> _distances = new(System.StringComparer.OrdinalIgnoreCase);
    private int _lastStateVersion = -1;
    private float _lastProximitySort;
    private TrackerSortMode _lastSortMode;

    // Per-quest cached step index for detecting step advances
    private readonly Dictionary<string, int> _cachedStepIndex = new(System.StringComparer.OrdinalIgnoreCase);

    // When true, the tracker renders as minimal floating text (no background,
    // no title bar, no header). Driven by previous frame's hover state.
    private bool _compact = true;

    // Content bounds from last frame, used to draw fitted tint backdrop
    // before the current frame's widgets (so the rect is behind the text).
    private Vector2 _contentMin;
    private Vector2 _contentMax;

    public bool Visible => _visible;
    public void Toggle() => _visible = !_visible;
    public void Show() => _visible = true;
    public void Hide() => _visible = false;

    public TrackerWindow(
        GuideData data, QuestStateTracker state, NavigationController nav,
        TrackerState tracker, GuideWindow guide, GuideConfig config)
    {
        _data = data;
        _state = state;
        _nav = nav;
        _tracker = tracker;
        _guide = guide;
        _config = config;

        // Subscribe to TrackerState events for animation triggers
        _tracker.Tracked += OnQuestTracked;
        _tracker.Untracked += OnQuestUntracked;
        _tracker.QuestCompleted += OnQuestCompleted;
        _tracker.StepAdvanced += OnQuestStepAdvanced;
    }

    public void Dispose()
    {
        _tracker.Tracked -= OnQuestTracked;
        _tracker.Untracked -= OnQuestUntracked;
        _tracker.QuestCompleted -= OnQuestCompleted;
        _tracker.StepAdvanced -= OnQuestStepAdvanced;
    }

    // ── Event handlers ───────────────────────────────────────────────

    private void OnQuestTracked(string dbName)
    {
        _animations[dbName] = new EntryAnimation { AddedAt = UnityEngine.Time.realtimeSinceStartup };
        _fadingOut.Remove(dbName); // cancel fade-out if re-tracked
        _visible = true; // show tracker when a quest is tracked
    }

    private void OnQuestUntracked(string dbName)
    {
        // Entry is already removed from TrackerState. Start fade-out
        // animation so it disappears gracefully when the window is visible.
        _fadingOut[dbName] = UnityEngine.Time.realtimeSinceStartup;
        _completionTimers.Remove(dbName);
    }

    private void OnQuestCompleted(string dbName)
    {
        var anim = GetOrDefaultAnim(dbName);
        anim.CompletedAt = UnityEngine.Time.realtimeSinceStartup;
        _animations[dbName] = anim;
        // Schedule auto-untrack after the flash duration
        _completionTimers[dbName] = UnityEngine.Time.realtimeSinceStartup;
    }

    private void OnQuestStepAdvanced(string dbName)
    {
        var anim = GetOrDefaultAnim(dbName);
        anim.StepAdvancedAt = UnityEngine.Time.realtimeSinceStartup;
        _animations[dbName] = anim;
    }

    // ── Draw ─────────────────────────────────────────────────────────

    /// <summary>
    /// Call from the ImGuiRenderer.OnLayout callback.
    /// Renders the tracker overlay when visible.
    /// </summary>
    public void Draw()
    {
        if (!_visible || !_tracker.Enabled) return;

        // Hide when a non-permanent game window overlaps us. Uses
        // previous frame's content bounds (stable — tracker isn't being
        // dragged while a game window opens). On the first frame before
        // any content has been drawn, _contentMax.Y == 0 so we skip the
        // check rather than suppress based on a zero rect.
        if (_contentMax.Y > _contentMin.Y
            && GameWindowOverlap.ShouldSuppressTracker(
                _contentMin.X, _contentMin.Y, _contentMax.X, _contentMax.Y))
            return;

        PruneAnimations();
        DetectStepAdvances();
        RebuildSortedListIfNeeded();

        if (_sorted.Count == 0 && _fadingOut.Count == 0)
            return;

        var cond = _config.LayoutResetRequested ? ImGuiCond.Always : ImGuiCond.FirstUseEver;
        var scale = _config.ResolvedUiScale;
        var display = ImGui.GetIO().DisplaySize;
        ImGui.SetNextWindowSize(new Vector2(DefaultWidth * scale, DefaultHeight * scale), cond);
        ImGui.SetNextWindowPos(
            new Vector2(40f, display.Y * 0.5f), cond,
            new Vector2(0f, 0.5f));

        // Compact mode: transparent background and chrome, same layout.
        // Expanded mode: full window with visible title bar and header.
        // _compact is set from the previous frame's hover state.
        // All elements occupy space in both modes to prevent layout jumps.
        int extraColors = 0;
        int extraVars = 0;
        Theme.PushWindowStyle();
        if (_compact)
        {
            // Fully transparent window — the tint backdrop is drawn
            // manually in DrawQuestList to cover only actual content.
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

        // Draw fitted tint backdrop using last frame's content bounds.
        // Uses the background draw list so the rect appears behind all
        // ImGui content, and is not clipped by the child scroll region.
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

        // ###Tracker keeps a stable window ID across modes.
        // Compact: empty display title + no ref bool = no text, no X button.
        // Expanded: "Quest Tracker" display title + ref bool = title + close.
        bool beginOpen;
        if (_compact)
            beginOpen = ImGui.Begin("###Tracker", flags);
        else
            beginOpen = ImGui.Begin("Quest Tracker###Tracker", ref _visible, flags);
        if (beginOpen)
        {
            // Header bar always occupies space; invisible in compact mode.
            if (_compact)
                ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0f);
            DrawHeaderBar();
            if (_compact)
                ImGui.PopStyleVar();

            DrawQuestList();

            // Update compact state from this frame for next frame.
            // Hover alone drives expanded mode. For resize/drag stability,
            // also stay expanded while the mouse button is held on a focused
            // window — but not on passive focus (e.g. another window closing
            // or F6 reload transferring focus here).
            bool hovered = ImGui.IsWindowHovered(ImGuiHoveredFlags.RootAndChildWindows);
            bool activeInteraction = ImGui.IsWindowFocused(ImGuiFocusedFlags.RootAndChildWindows)
                && ImGui.IsMouseDown(ImGuiMouseButton.Left);
            _compact = !hovered && !activeInteraction;

            // Release passive focus so the next click doesn't briefly
            // flash chrome before focus moves elsewhere.
            if (_compact && ImGui.IsWindowFocused(ImGuiFocusedFlags.RootAndChildWindows))
                ImGui.SetWindowFocus(null);
        }

        Theme.ClampWindowPosition();

        ImGui.End();
        if (extraColors > 0)
            ImGui.PopStyleColor(extraColors);
        if (extraVars > 0)
            ImGui.PopStyleVar(extraVars);
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
        bool active = _tracker.SortMode == mode;
        if (active)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);

        if (ImGui.SmallButton(label + "##tsort"))
        {
            _tracker.SortMode = mode;
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
        ImGui.BeginChild("##TrackerScroll", Vector2.Zero, false);

        // Record content top for next frame's backdrop.
        var contentTop = ImGui.GetCursorScreenPos();

        for (int i = 0; i < _sorted.Count; i++)
        {
            var dbName = _sorted[i];
            var quest = _data.GetByDBName(dbName);
            if (quest == null) continue;

            DrawQuestEntry(quest, dbName, i);
        }

        // Record bounds for next frame's backdrop with per-side padding
        // tuned so the visual gap looks even despite ImGui's internal
        // window padding and trailing item spacing.
        var contentBottom = ImGui.GetCursorScreenPos();
        var childPos = ImGui.GetWindowPos();
        float childWidth = ImGui.GetWindowWidth();
        float childHeight = ImGui.GetWindowHeight();
        float itemSpacing = ImGui.GetStyle().ItemSpacing.Y;
        // Clamp bottom to visible child bounds so off-screen scrolled
        // entries don't extend the backdrop past the window edge.
        // When content fits, subtract trailing item spacing; when
        // scrolling, use the child's visible bottom edge directly.
        float visibleBottom = childPos.Y + childHeight;
        float bottomY = contentBottom.Y <= visibleBottom
            ? contentBottom.Y - itemSpacing + CompactPadBottom
            : visibleBottom + CompactPadBottom;
        _contentMin = new Vector2(childPos.X - CompactPadLeft, childPos.Y - CompactPadTop);
        _contentMax = new Vector2(childPos.X + childWidth + CompactPadRight, bottomY);

        ImGui.EndChild();
    }

    private void DrawQuestEntry(QuestEntry quest, string dbName, int index)
    {
        var anim = GetOrDefaultAnim(dbName);
        float now = UnityEngine.Time.realtimeSinceStartup;
        bool isFadingOut = _fadingOut.TryGetValue(dbName, out float fadeStart);

        // Entry is neither tracked nor fading out — stale sorted list entry
        if (!isFadingOut && !_tracker.IsTracked(dbName)) return;
        // Compute entry alpha for fade-in or fade-out
        float entryAlpha = 1f;
        if (isFadingOut)
        {
            float elapsed = now - fadeStart;
            entryAlpha = UnityEngine.Mathf.Clamp01(1f - elapsed / FadeOutDuration);
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

        // Tint text color for completion flash (green) or step advance (yellow)
        bool tinted = false;
        if (anim.CompletedAt > 0 && now - anim.CompletedAt < CompletionFlashDuration)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Success);
            tinted = true;
        }
        else if (anim.StepAdvancedAt > 0 && now - anim.StepAdvancedAt < StepAdvanceDuration)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
            tinted = true;
        }

        // Line 1: [NAV] Quest Name  Lv##
        bool navEnabled = _config.ShowArrow.Value || _config.ShowGroundPath.Value;
        if (navEnabled)
        {
            DrawNavButton(quest);
            ImGui.SameLine();
        }
        DrawQuestNameAndLevel(quest);

        // Line 2: indented step description
        DrawCurrentStep(quest);

        // Right-click context menu
        if (ImGui.BeginPopupContextItem($"##ctx{quest.DBName}"))
        {
            if (ImGui.Selectable("Untrack"))
                _tracker.Untrack(quest.DBName);
            if (ImGui.Selectable("Open in Guide"))
            {
                _state.SelectQuest(quest.DBName);
                _guide.Show();
            }
            ImGui.EndPopup();
        }

        // Prerequisite line if blocked
        DrawPrerequisites(quest);

        ImGui.Spacing();

        if (tinted)
            ImGui.PopStyleColor();
        if (entryAlpha < 1f)
            ImGui.PopStyleVar();

        ImGui.PopID();
    }

    // ── NAV button ───────────────────────────────────────────────────

    private void DrawNavButton(QuestEntry quest)
    {
        var (rawStep, displayStep, displayQuest) = GetCurrentStep(quest);
        bool navigable = displayStep?.TargetKey != null;
        bool isActive = rawStep != null && _nav.IsNavigating(quest.DBName, rawStep.Order);

        if (!navigable)
        {
            ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0.3f);
            ImGui.SmallButton("[NAV]");
            ImGui.PopStyleVar();

            if (ImGui.IsItemHovered(ImGuiHoveredFlags.AllowWhenDisabled))
            {
                ImGui.BeginTooltip();
                ImGui.TextUnformatted("No navigable target");
                ImGui.EndTooltip();
            }
            return;
        }

        if (isActive)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.QuestActive);

        if (ImGui.SmallButton("[NAV]"))
        {
            if (isActive)
                _nav.Clear();
            else
                // Pass raw step + original quest. NavigateTo captures the
                // origin identity and resolves sub-quests internally.
                _nav.NavigateTo(rawStep!, quest, _state.CurrentZone);
        }

        if (isActive)
            ImGui.PopStyleColor();

        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            ImGui.TextUnformatted(isActive ? "Stop navigating" : "Navigate to current step");
            ImGui.EndTooltip();
        }
    }

    // ── Quest name + level ───────────────────────────────────────────

    private void DrawQuestNameAndLevel(QuestEntry quest)
    {
        // Match guide list format: level prefix + quest name in status color
        string label = quest.LevelEstimate?.Recommended is int lvl
            ? $"{lvl,2}  {quest.DisplayName}"
            : $"    {quest.DisplayName}";

        // Append distance or source label (e.g. "Fishing")
        if (_distances.TryGetValue(quest.DBName, out var dist))
        {
            if (dist.HasDistance)
                label += $" ({dist.Meters:0}m)";
            else if (dist.HasLabel)
                label += $" ({dist.Label})";
        }

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.GetQuestColor(_state, quest.DBName));
        if (ImGui.Selectable(label + "##name" + quest.DBName))
        {
            _state.SelectQuest(quest.DBName);
            _guide.Show();
        }
        ImGui.PopStyleColor();
    }

    // ── Current step ─────────────────────────────────────────────────

    private void DrawCurrentStep(QuestEntry quest)
    {
        var (_, step, resolvedQuest) = GetCurrentStep(quest);

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        if (step == null)
        {
            ImGui.TextWrapped(quest.HasSteps ? "Completed" : "No guide data available.");
            ImGui.PopStyleColor();
            ImGui.Unindent(Theme.IndentWidth);
            return;
        }

        string text = FormatStepText(resolvedQuest, step);
        bool isCrossZone = _distances.TryGetValue(quest.DBName, out var stepDist) && !stepDist.InCurrentZone;

        // For cross-zone non-travel steps, show "Travel to {zone}" instead
        // of the step description. Travel steps already say where to go.
        if (isCrossZone && step.Action != "travel")
        {
            var zone = TrackerSorter.GetStepZoneName(quest, _state, _data);
            if (zone != null)
                text = $"Travel to {zone}.";
        }

        ImGui.TextWrapped(text);

        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);
    }

    private string FormatStepText(QuestEntry quest, QuestStep step)
    {
        if (step.Quantity.HasValue && step.TargetKey != null)
        {
            int have = _state.CountItem(step.TargetKey);
            int need = step.Quantity.Value;
            return $"{step.Description} ({have}/{need})";
        }

        return step.Description;
    }

    // ── Prerequisites ────────────────────────────────────────────────

    private void DrawPrerequisites(QuestEntry quest)
    {
        if (quest.Prerequisites == null || quest.Prerequisites.Count == 0) return;

        foreach (var pre in quest.Prerequisites)
        {
            if (pre.Item != null) continue;
            if (_state.IsCompleted(pre.QuestKey)) continue;

            ImGui.Indent(Theme.IndentWidth);
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0.6f);

            if (ImGui.Selectable($"Requires: {pre.QuestName}##prereq{pre.QuestKey}"))
            {
                _state.SelectQuest(pre.QuestKey);
                _guide.Show();
            }

            ImGui.PopStyleVar();
            ImGui.PopStyleColor();
            ImGui.Unindent(Theme.IndentWidth);
            break; // Show only the first blocking prerequisite
        }
    }

    // ── Animation management ─────────────────────────────────────────

    /// <summary>
    /// Clean up expired animations and handle completion→untrack lifecycle.
    /// </summary>
    private void PruneAnimations()
    {
        float now = UnityEngine.Time.realtimeSinceStartup;

        // Auto-untrack completed quests after the flash duration
        var toUntrack = new List<string>();
        foreach (var (dbName, startTime) in _completionTimers)
        {
            if (now - startTime > CompletionLingerDuration)
                toUntrack.Add(dbName);
        }
        foreach (var dbName in toUntrack)
        {
            _completionTimers.Remove(dbName);
            _tracker.Untrack(dbName); // fires OnQuestUntracked → starts fade-out
        }

        // Remove expired fade-out entries
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
            _cachedStepIndex.Remove(dbName);
        }
    }

    // ── Sort management ──────────────────────────────────────────────

    private void RebuildSortedListIfNeeded()
    {
        bool trackerDirty = _tracker.IsDirty;
        bool stateDirty = _state.Version != _lastStateVersion;
        bool sortModeChanged = _tracker.SortMode != _lastSortMode;

        // Distances are displayed in all sort modes, so refresh
        // periodically to keep them current as the player moves.
        bool distancesStale = UnityEngine.Time.realtimeSinceStartup - _lastProximitySort > 2f;

        if (trackerDirty || stateDirty || sortModeChanged || distancesStale)
        {
            if (stateDirty) _lastStateVersion = _state.Version;
            RebuildSortedList();
        }
    }

    private void RebuildSortedList()
    {
        _sorted.Clear();
        _sorted.AddRange(_tracker.TrackedQuests);

        // Append fading-out entries at their last position so they
        // fade in place rather than jumping to the bottom
        foreach (var dbName in _fadingOut.Keys)
        {
            if (!_sorted.Contains(dbName))
                _sorted.Add(dbName);
        }
        _lastSortMode = _tracker.SortMode;
        _lastProximitySort = UnityEngine.Time.realtimeSinceStartup;

        // Compute distances once — used by proximity sort and by
        // DrawQuestNameAndLevel to display distance for same-zone quests.
        if (GameData.PlayerControl != null)
        {
            var playerPos = GameData.PlayerControl.transform.position;
            TrackerSorter.ComputeDistances(_sorted, _data, _state, _nav, playerPos, _distances);
        }
        else
        {
            _distances.Clear();
        }

        TrackerSorter.Sort(_sorted, _tracker.SortMode, _data,
            _distances.Count > 0 ? _distances : null);
    }

    // ── Step advance detection ───────────────────────────────────────

    private void DetectStepAdvances()
    {
        foreach (var dbName in _tracker.TrackedQuests)
        {
            var quest = _data.GetByDBName(dbName);
            if (quest?.Steps == null) continue;

            int idx = StepProgress.GetCurrentStepIndex(quest, _state, _data);

            if (_cachedStepIndex.TryGetValue(dbName, out int prev))
            {
                if (idx > prev)
                    _tracker.OnStepAdvanced(dbName);
            }
            _cachedStepIndex[dbName] = idx;
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────

    /// <summary>
    /// Get the current step for display and navigation.
    /// Returns the raw step (from the parent quest, for navigation identity),
    /// the resolved display step (from sub-quest, for text/icon rendering),
    /// and the resolved quest (for inventory count formatting).
    /// </summary>
    private (QuestStep? rawStep, QuestStep? displayStep, QuestEntry displayQuest) GetCurrentStep(QuestEntry quest)
    {
        if (quest.Steps == null || quest.Steps.Count == 0) return (null, null, quest);
        int idx = StepProgress.GetCurrentStepIndex(quest, _state, _data);
        var raw = idx < quest.Steps.Count ? quest.Steps[idx] : null;
        if (raw == null) return (null, null, quest);
        var (resolved, resolvedQuest) = StepProgress.ResolveActiveStep(raw, quest, _state, _data);
        return (raw, resolved, resolvedQuest ?? quest);
    }

    private EntryAnimation GetOrDefaultAnim(string dbName) =>
        _animations.TryGetValue(dbName, out var anim) ? anim : default;


    // ── Animation data ───────────────────────────────────────────────

    private struct EntryAnimation
    {
        public float AddedAt;
        public float CompletedAt;
        public float StepAdvancedAt;
    }
}
