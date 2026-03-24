using System.Numerics;
using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Compact always-visible quest tracker overlay rendered via Dear ImGui.
/// Shows tracked quest objectives with navigation integration, sorting,
/// and state change animations. Peer to GuideWindow — wired into the
/// same OnLayout callback.
///
/// Per entry (two lines):
///   [NAV] Quest Name                  Lv##
///     Step description (3/5)
///
/// Interactions:
///   - Left-click quest name → open full guide to that quest
///   - [NAV] button → toggle GPS navigation for current step
///   - Right-click → context menu with Untrack
///   - Sort buttons in header bar
/// </summary>
public sealed class TrackerWindow
{
    private const float DefaultWidth = 280f;
    private const float DefaultHeight = 200f;
    private const float MinVisible = 40f;

    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly NavigationController _nav;
    private readonly TrackerState _tracker;
    private readonly GuideWindow _guide;
    private readonly GuideConfig _config;

    private bool _visible = true;
    private bool _firstDraw = true;

    // Sorted working copy of tracked quest DB names — rebuilt on dirty
    private readonly List<string> _sorted = new();
    private int _lastTrackerVersion;
    private int _lastStateVersion;
    private float _lastProximitySort;
    private TrackerSortMode _lastSortMode;

    // Per-quest cached step index for detecting step advances
    private readonly Dictionary<string, int> _cachedStepIndex = new(System.StringComparer.OrdinalIgnoreCase);

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
    }

    /// <summary>
    /// Call from the ImGuiRenderer.OnLayout callback.
    /// Renders the tracker overlay when visible.
    /// </summary>
    public void Draw()
    {
        if (!_visible) return;

        _tracker.PruneCompleted();
        DetectStepAdvances();
        RebuildSortedListIfNeeded();

        if (_sorted.Count == 0 && _tracker.TrackedQuests.Count == 0)
            return;

        // Two-state opacity: subtle when idle, opaque on hover
        float bgAlpha = _config.TrackerIdleOpacity.Value;

        if (_firstDraw)
        {
            ImGui.SetNextWindowSize(new Vector2(DefaultWidth, DefaultHeight), ImGuiCond.FirstUseEver);
            float savedX = _config.TrackerWindowX.Value;
            float savedY = _config.TrackerWindowY.Value;
            if (savedX >= 0 && savedY >= 0)
                ImGui.SetNextWindowPos(new Vector2(savedX, savedY), ImGuiCond.FirstUseEver);
            _firstDraw = false;
        }

        ImGui.SetNextWindowBgAlpha(bgAlpha);
        ImGui.PushStyleColor(ImGuiCol.WindowBg, Theme.Background);
        ImGui.PushStyleColor(ImGuiCol.ChildBg, Theme.Surface);

        var flags = ImGuiWindowFlags.NoCollapse
            | ImGuiWindowFlags.NoFocusOnAppearing
            | ImGuiWindowFlags.NoNav
            | ImGuiWindowFlags.NoBringToFrontOnFocus;

        if (ImGui.Begin("Quest Tracker", ref _visible, flags))
        {
            // Switch to hover opacity if mouse is over the window
            if (ImGui.IsWindowHovered(ImGuiHoveredFlags.RootAndChildWindows))
                ImGui.SetNextWindowBgAlpha(_config.TrackerHoverOpacity.Value);

            DrawHeaderBar();
            DrawQuestList();
        }

        ClampWindowPosition();
        ImGui.End();
        ImGui.PopStyleColor(2);
    }

    /// <summary>Save window position to config for cross-session persistence.</summary>
    public void SavePosition()
    {
        if (_config == null) return;
        var pos = ImGui.GetWindowPos();
        var size = ImGui.GetWindowSize();
        _config.TrackerWindowX.Value = pos.X;
        _config.TrackerWindowY.Value = pos.Y;
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

        for (int i = 0; i < _sorted.Count; i++)
        {
            var dbName = _sorted[i];
            var quest = _data.GetByDBName(dbName);
            if (quest == null) continue;

            DrawQuestEntry(quest, i);
        }

        ImGui.EndChild();
    }

    private void DrawQuestEntry(QuestEntry quest, int index)
    {
        var anim = _tracker.GetAnimation(quest.DBName);
        float now = UnityEngine.Time.realtimeSinceStartup;

        // Compute entry alpha for fade-in/fade-out animations
        float entryAlpha = 1f;
        if (anim.PendingRemoval && anim.RemoveAt > 0)
        {
            float elapsed = now - anim.RemoveAt;
            entryAlpha = UnityEngine.Mathf.Clamp01(1f - elapsed / 0.3f);
        }
        else if (anim.AddedAt > 0)
        {
            float elapsed = now - anim.AddedAt;
            if (elapsed < 0.3f)
                entryAlpha = elapsed / 0.3f;
        }

        if (entryAlpha <= 0f) return;

        ImGui.PushID(index);

        if (entryAlpha < 1f)
            ImGui.PushStyleVar(ImGuiStyleVar.Alpha, entryAlpha);

        // Tint text color for completion flash (green) or step advance (yellow)
        bool tinted = false;
        if (anim.CompletedAt > 0 && now - anim.CompletedAt < 1.5f)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Success);
            tinted = true;
        }
        else if (anim.StepAdvancedAt > 0 && now - anim.StepAdvancedAt < 0.8f)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
            tinted = true;
        }
        // Line 1: [NAV] Quest Name  Lv##
        DrawNavButton(quest);
        ImGui.SameLine();
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
        var step = GetCurrentStep(quest);
        bool navigable = step?.TargetKey != null;
        bool isActive = step != null && _nav.IsNavigating(quest.DBName, step.Order);

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
                _nav.NavigateTo(step!, quest, _state.CurrentZone);
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
        // Quest name — clickable to open in guide
        ImGui.PushStyleColor(ImGuiCol.Header, 0);
        ImGui.PushStyleColor(ImGuiCol.HeaderHovered, Theme.Surface);
        ImGui.PushStyleColor(ImGuiCol.HeaderActive, Theme.Surface);

        if (ImGui.Selectable(quest.DisplayName, false, ImGuiSelectableFlags.None))
        {
            _state.SelectQuest(quest.DBName);
            _guide.Show();
        }

        ImGui.PopStyleColor(3);

        // Level right-aligned on same line
        int? level = quest.LevelEstimate?.Recommended;
        if (level.HasValue)
        {
            var levelText = $"Lv{level.Value}";
            float availWidth = ImGui.GetContentRegionAvail().X;
            float textWidth = ImGui.CalcTextSize(levelText).X;
            ImGui.SameLine(ImGui.GetCursorPosX() + availWidth - textWidth);
            ImGui.PushStyleColor(ImGuiCol.Text, GetLevelColor(level.Value));
            ImGui.TextUnformatted(levelText);
            ImGui.PopStyleColor();
        }
    }

    // ── Current step ─────────────────────────────────────────────────

    private void DrawCurrentStep(QuestEntry quest)
    {
        var step = GetCurrentStep(quest);
        if (step == null) return;

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        string text = FormatStepText(quest, step);
        ImGui.TextWrapped(text);

        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);
    }

    private string FormatStepText(QuestEntry quest, QuestStep step)
    {
        // For collect steps, append progress
        if (step.Quantity.HasValue && step.TargetName != null)
        {
            int have = _state.CountItemInInventory(step.TargetName);
            int need = step.Quantity.Value;
            return $"{step.Description} ({have}/{need})";
        }

        return step.Description;
    }

    // ── Prerequisites ────────────────────────────────────────────────

    private void DrawPrerequisites(QuestEntry quest)
    {
        if (quest.Prerequisites == null || quest.Prerequisites.Count == 0) return;

        // Show only incomplete prerequisites
        foreach (var pre in quest.Prerequisites)
        {
            // Skip item prerequisites (those are acquisition chains, not blocking)
            if (pre.Item != null) continue;
            if (_state.IsCompleted(pre.QuestKey)) continue;

            ImGui.Indent(Theme.IndentWidth);
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0.6f);

            if (ImGui.Selectable($"Requires: {pre.QuestName}##prereq{pre.QuestKey}", false, ImGuiSelectableFlags.None))
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

    // ── Flash overlays ───────────────────────────────────────────────

    private static void DrawFlashOverlay(TrackerState.EntryAnimation anim, float now)
    {
        // Flash animations use text color tinting applied by the caller
        // via PushStyleColor rather than DrawList overlays. DrawList
        // AddRectFilled with System.Numerics.Vector2 crashes after
        // ILRepack merges the assembly (same P/Invoke marshalling issue
        // that affects all DrawList Vector2 parameters).
    }

    // ── Sort management ──────────────────────────────────────────────

    private void RebuildSortedListIfNeeded()
    {
        bool trackerDirty = _tracker.IsDirty;
        bool stateDirty = _state.IsDirty;
        bool sortModeChanged = _tracker.SortMode != _lastSortMode;
        bool proximityStale = _tracker.SortMode == TrackerSortMode.Proximity
            && UnityEngine.Time.realtimeSinceStartup - _lastProximitySort > 2f;

        if (trackerDirty || stateDirty || sortModeChanged || proximityStale)
            RebuildSortedList();
    }

    private void RebuildSortedList()
    {
        _sorted.Clear();
        _sorted.AddRange(_tracker.TrackedQuests);
        _lastSortMode = _tracker.SortMode;
        _lastProximitySort = UnityEngine.Time.realtimeSinceStartup;

        UnityEngine.Vector3? playerPos = GameData.PlayerControl?.transform.position;
        TrackerSorter.Sort(_sorted, _tracker.SortMode, _data, _state, playerPos);
    }

    // ── Step advance detection ───────────────────────────────────────

    private void DetectStepAdvances()
    {
        foreach (var dbName in _tracker.TrackedQuests)
        {
            var quest = _data.GetByDBName(dbName);
            if (quest?.Steps == null) continue;

            int idx = StepProgress.GetCurrentStepIndex(quest, _state);

            if (_cachedStepIndex.TryGetValue(dbName, out int prev))
            {
                if (idx > prev)
                    _tracker.OnStepAdvanced(dbName);
            }
            _cachedStepIndex[dbName] = idx;
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────

    private QuestStep? GetCurrentStep(QuestEntry quest)
    {
        if (quest.Steps == null || quest.Steps.Count == 0) return null;
        int idx = StepProgress.GetCurrentStepIndex(quest, _state);
        return idx < quest.Steps.Count ? quest.Steps[idx] : null;
    }

    private static uint GetLevelColor(int level)
    {
        // TODO: compare against player level when available
        // For now, use the warning color for visibility
        return Theme.TextSecondary;
    }

    private static void ClampWindowPosition()
    {
        var pos = ImGui.GetWindowPos();
        var size = ImGui.GetWindowSize();
        var display = ImGui.GetIO().DisplaySize;

        float x = pos.X;
        float y = pos.Y;

        if (x + size.X < MinVisible) x = MinVisible - size.X;
        if (x > display.X - MinVisible) x = display.X - MinVisible;
        if (y > display.Y - MinVisible) y = display.Y - MinVisible;
        if (y < 0) y = 0;

        if (x != pos.X || y != pos.Y)
            ImGui.SetWindowPos(new Vector2(x, y));
    }
}
