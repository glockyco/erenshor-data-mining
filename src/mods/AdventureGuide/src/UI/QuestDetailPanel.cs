using AdventureGuide.Config;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders the right-side quest detail view using Dear ImGui.
/// Sections ordered by importance: Header, Objectives, Rewards, Prerequisites, Chain.
/// </summary>
public sealed class QuestDetailPanel
{
    private readonly GuideData _data;
    private readonly QuestStateTracker _state;
    private readonly NavigationController _nav;
    private readonly TrackerState _tracker;
    private readonly GuideConfig _config;

    // Rebuilt only when selection or quest/inventory/workflow state changes.
    // Pre-cache closed trees too, so opening a tree does not allocate.
    private readonly Dictionary<QuestEntry, QuestDisplayCache> _questDisplay = new();
    private readonly HashSet<string> _visited = new();
    private readonly List<string> _acquisitionLines = new();
    private readonly List<string> _completionLines = new();
    private readonly List<(string Text, bool Secondary)> _rewardLines = new();
    private readonly List<(Prerequisite Prerequisite, string Label)> _prerequisites = new();
    private HashSet<string>? _stepTreeQuestKeys;
    private string? _cachedQuestKey;
    private int _cachedVersion = -1;
    private string? _levelZoneLine;

    /// <summary>Max sub-quest nesting depth to prevent runaway recursion.</summary>
    private const int MaxSubQuestDepth = 5;

    public QuestDetailPanel(
        GuideData data,
        QuestStateTracker state,
        NavigationController nav,
        TrackerState tracker,
        GuideConfig config
    )
    {
        _data = data;
        _state = state;
        _nav = nav;
        _tracker = tracker;
        _config = config;
    }

    public void Draw()
    {
        if (_cachedQuestKey != _state.SelectedQuestKey || _cachedVersion != _state.Version)
        {
            _cachedQuestKey = _state.SelectedQuestKey;
            _cachedVersion = _state.Version;
            RebuildDisplayCache();
        }

        if (_state.SelectedQuestKey == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped("Select a quest from the list.");
            ImGui.PopStyleColor();
            return;
        }

        var quest = _data.GetByRuntimeKey(_state.SelectedQuestKey);
        if (quest == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped("Quest not found in guide data.");
            ImGui.PopStyleColor();
            return;
        }

        DrawHeader(quest);
        DrawObjectives(quest);
        DrawRewards(quest);
        DrawPrerequisites(quest);
    }

    // ── Header ──────────────────────────────────────────────────────

    private void DrawHeader(QuestEntry quest)
    {
        // Track/Untrack button inline before quest name
        if (_tracker.Enabled)
        {
            bool tracked = _tracker.IsTracked(quest.RuntimeKey);
            bool completed = _state.IsCompleted(quest);
            if (!completed || tracked)
            {
                if (tracked)
                    ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);
                if (ImGui.SmallButton(tracked ? "[Untrack]" : "[Track]"))
                {
                    if (tracked)
                        _tracker.Untrack(quest.RuntimeKey);
                    else
                        _tracker.Track(quest.RuntimeKey);
                }
                if (tracked)
                    ImGui.PopStyleColor();
                ImGui.SameLine();
            }
        }

        // Quest name in header color
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();

        // Level + zone on one line (replaces separate "Zone:" line)
        DrawLevelZoneLine(quest);

        // All acquisition sources (not just dialog)
        foreach (var line in _acquisitionLines)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text(line);
            ImGui.PopStyleColor();
        }

        // Turn-in location
        foreach (var line in _completionLines)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text(line);
            ImGui.PopStyleColor();
        }

        // Description
        if (quest.Description != null)
        {
            ImGui.Spacing();
            ImGui.TextWrapped(quest.Description);
        }

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();
    }

    private void DrawLevelZoneLine(QuestEntry quest)
    {
        if (_levelZoneLine == null)
            return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        ImGui.Text(_levelZoneLine);

        // Tooltip: show all steps with their levels, mark the driving step
        if (ImGui.IsItemHovered() && quest.Steps is { Count: > 0 })
        {
            ImGui.BeginTooltip();
            ImGui.Text("Quest level: hardest step");
            ImGui.Separator();
            int? questLvl = quest.LevelEstimate?.Recommended;
            foreach (var step in quest.Steps)
            {
                int? stepLvl = step.LevelEstimate?.Recommended;
                string lvlStr = stepLvl.HasValue ? $"Lv {stepLvl, 2}" : "    ";
                bool isDriving = questLvl.HasValue && stepLvl == questLvl;
                string marker = isDriving ? " <" : "";
                uint tipColor = isDriving ? Theme.TextPrimary : Theme.TextSecondary;
                ImGui.PushStyleColor(ImGuiCol.Text, tipColor);
                ImGui.Text($"  {step.Order}. {step.Description}  {lvlStr}{marker}");
                ImGui.PopStyleColor();
            }
            ImGui.EndTooltip();
        }

        ImGui.PopStyleColor();
    }

    // ── Objectives ──────────────────────────────────────────────────

    private void DrawObjectives(QuestEntry quest)
    {
        if (!quest.HasSteps)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped("No guide data available for this quest.");
            ImGui.PopStyleColor();
            return;
        }

        if (_state.Workflows.IsUnverifiable(quest))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Warning);
            ImGui.TextWrapped(
                "Workflow state is ambiguous after reload. Re-enter the trigger area with the required item."
            );
            ImGui.PopStyleColor();
        }

        if (!ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        _visited.Clear();
        _visited.Add(quest.StableKey);
        ImGui.Indent();
        DrawSteps(quest, _visited);
        ImGui.Unindent();
    }

    /// <summary>
    /// Render a quest's step list with or-group separators and step state coloring.
    /// Reused for both top-level objectives and inline sub-quest rendering.
    /// Caller handles indentation; this method handles PushID scoping.
    /// </summary>
    private void DrawSteps(QuestEntry quest, HashSet<string> visited)
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return;

        ImGui.PushID(quest.RuntimeKey);

        int currentStepIndex = _questDisplay[quest].CurrentStepIndex;
        string? prevOrGroup = null;

        for (int i = 0; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];

            // Show "OR" separator between consecutive steps in the same or_group
            if (step.OrGroup != null && step.OrGroup == prevOrGroup)
            {
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                ImGui.Text("  -- OR --");
                ImGui.PopStyleColor();
            }

            StepState state;
            if (i < currentStepIndex)
                state = StepState.Completed;
            else if (i == currentStepIndex)
                state = StepState.Current;
            else
                state = StepState.Future;

            DrawStep(step, state, quest, visited);

            prevOrGroup = step.OrGroup;
        }

        ImGui.PopID();
    }

    private enum StepState
    {
        Completed,
        Current,
        Future,
    }

    private void DrawStep(
        QuestStep step,
        StepState state,
        QuestEntry quest,
        HashSet<string> visited
    )
    {
        uint color = state switch
        {
            StepState.Completed => Theme.QuestCompleted,
            StepState.Current => Theme.QuestActive,
            _ => Theme.TextPrimary,
        };
        var display = _questDisplay[quest].Steps[step];

        // Collect steps: show have/need count and override color
        // when items are in hand, regardless of step pointer position.
        if (
            (step.Action is "collect" or "obtain")
            && step.TargetKey != null
            && step.Quantity.HasValue
        )
        {
            if (display.HasRequiredQuantity)
                color = Theme.QuestCompleted;
        }

        // Complete-quest steps: override color when target quest is done.
        if (step.Action == "complete_quest" && step.TargetKey != null)
        {
            var target = _data.GetByStableKey(step.TargetKey);
            if (target != null && _state.IsCompleted(target))
                color = Theme.QuestCompleted;
        }

        // Step suffix (zone and level) is cached with the have/need count.

        // [NAV] button first (fixed width), then step text
        DrawNavButton(step, quest);

        ImGui.PushStyleColor(ImGuiCol.Text, color);
        ImGui.Text(display.Text);
        ImGui.PopStyleColor();

        // Drop/vendor sources and tips for collect steps
        DrawStepSources(step, quest, visited);

        // Sub-quest tree for complete_quest steps: show the target
        // quest's steps inline so the player sees what they need to do.
        DrawSubQuestSteps(step, quest, visited);

        // Show alternative zone lines when cross-zone navigating this step
        if (_nav.IsNavigating(quest.RuntimeKey, step.Order))
        {
            var alternatives = _nav.GetAlternativeZoneLines(_state.CurrentZone);
            if (alternatives.Count > 1)
                DrawZoneLineAlternatives(alternatives, step);
        }
    }

    private bool IsNavigationEnabled => _config.ShowArrow.Value || _config.ShowGroundPath.Value;

    private void DrawNavButton(QuestStep step, QuestEntry quest)
    {
        if (!IsNavigationEnabled)
            return;
        if (step.TargetKey == null)
            return;

        // Character targets need spawn data; item targets need at least one
        // available source with spawn data or a scene.
        var display = _questDisplay[quest].Steps[step];
        bool navigable = display.Navigable;
        bool isActive = _nav.IsNavigating(quest.RuntimeKey, step.Order);

        if (!navigable)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0.4f);
            ImGui.SmallButton(display.NavLabel);
            ImGui.PopStyleVar();
            ImGui.PopStyleColor();

            if (ImGui.IsItemHovered(ImGuiHoveredFlags.AllowWhenDisabled))
            {
                ImGui.BeginTooltip();
                ImGui.Text("No known source");
                ImGui.EndTooltip();
            }

            ImGui.SameLine();
            return;
        }

        if (isActive)
            ImGui.PushStyleColor(ImGuiCol.Button, Theme.QuestActive);

        if (ImGui.SmallButton(display.NavLabel))
        {
            if (isActive)
                _nav.Clear();
            else
                _nav.NavigateTo(step, quest, _state.CurrentZone);
        }

        if (isActive)
            ImGui.PopStyleColor();

        if (ImGui.IsItemHovered())
        {
            ImGui.BeginTooltip();
            if (isActive)
                ImGui.Text("Click to stop navigating");
            else
                ImGui.Text($"Navigate to {step.TargetName ?? step.Description}");
            ImGui.EndTooltip();
        }

        // Keep cursor on same line so the step text follows the button
        ImGui.SameLine();
    }

    /// <summary>
    /// Show obtainability sources sorted by level (easiest first), with levels
    /// and counts inline. Sources arrive pre-sorted and pre-aggregated from
    /// the pipeline. Collapses beyond 4 sources behind a TreeNode.
    /// Available sources and their display labels are cached per state version.
    /// </summary>
    private void DrawStepSources(QuestStep step, QuestEntry quest, HashSet<string> visited)
    {
        if (
            (step.Action is not "collect" and not "obtain" and not "read")
            || step.TargetName == null
        )
        {
            DrawTips(step, quest);
            return;
        }

        var display = _questDisplay[quest].Steps[step];
        var visibleSources = display.VisibleSources;
        if (visibleSources.Count == 0)
        {
            DrawTips(step, quest);
            return;
        }

        ImGui.Indent();
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        const int maxVisible = 4;
        int visible = Math.Min(visibleSources.Count, maxVisible);

        for (int i = 0; i < visible; i++)
            DrawSource(visibleSources[i], quest, step, visited);

        if (visibleSources.Count > maxVisible)
        {
            if (ImGui.TreeNode(display.MoreSourcesLabel!))
            {
                for (int i = maxVisible; i < visibleSources.Count; i++)
                    DrawSource(visibleSources[i], quest, step, visited);
                ImGui.TreePop();
            }
        }

        ImGui.PopStyleColor();
        ImGui.Unindent();

        DrawTips(step, quest);
    }

    private void DrawZoneLineAlternatives(
        List<(ZoneLineEntry line, float distance, bool isSelected, bool isAccessible)> alternatives,
        QuestStep step
    )
    {
        ImGui.Indent();
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        string header = $"{alternatives.Count} zone connections";
        if (ImGui.TreeNode($"{header}##zl_{step.Order}"))
        {
            for (int i = 0; i < alternatives.Count; i++)
            {
                var (line, distance, isActive, isAccessible) = alternatives[i];
                if (!isAccessible)
                {
                    // Locked zone line: dimmed text
                    ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0.3f);
                    ImGui.Text($"To {line.DestinationDisplay} ({distance:F0}m)");
                    ImGui.PopStyleVar();

                    // Required quests as clickable links on the next line
                    if (line.RequiredQuestGroups != null)
                    {
                        foreach (var group in line.RequiredQuestGroups)
                        {
                            foreach (var questDBName in group)
                            {
                                if (_state.IsGameQuestCompleted(questDBName))
                                    continue;
                                var entry = _data.GetByDBName(questDBName);
                                if (entry == null)
                                    continue;
                                ImGui.Indent();
                                if (
                                    ImGui.Selectable(
                                        $"Requires: \"{entry.DisplayName}\"##rq_{step.Order}_{i}_{questDBName}"
                                    )
                                )
                                    _state.SelectQuest(entry);
                                ImGui.Unindent();
                            }
                            break; // show only the first group
                        }
                    }
                }
                else
                {
                    string label = $"To {line.DestinationDisplay} ({distance:F0}m)";

                    if (isActive)
                        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);

                    if (ImGui.Selectable($"{label}##zl_{step.Order}_{i}"))
                        _nav.PinZoneLine(line);

                    if (isActive)
                        ImGui.PopStyleColor();

                    if (ImGui.IsItemHovered())
                    {
                        ImGui.BeginTooltip();
                        ImGui.Text($"Route via {line.DestinationDisplay}");
                        ImGui.EndTooltip();
                    }
                }
            }
            ImGui.TreePop();
        }

        ImGui.PopStyleColor();
        ImGui.Unindent();
    }

    private void DrawSource(
        ItemSource src,
        QuestEntry quest,
        QuestStep step,
        HashSet<string> visited,
        int depth = 0
    )
    {
        if (!IsSourceAvailable(src))
            return;
        // Consistent format: {what}  ·  {where}  ·  Lv {N}
        var display = _questDisplay[quest].Steps[step].Sources[(src, depth)];
        string label = display.Label;

        // Quest reward with a resolvable sub-quest: render its steps inline
        if (src.Type == "quest_reward" && src.QuestKey != null)
        {
            var subQuest = _data.GetByStableKey(src.QuestKey);
            if (
                subQuest?.Steps is { Count: > 0 }
                && visited.Count <= MaxSubQuestDepth
                && !visited.Contains(subQuest.StableKey)
            )
            {
                DrawQuestRewardTree(subQuest, display, visited);
                return;
            }
        }

        // Non-quest-reward children (crafting ingredients, or quest_reward
        // fallback when sub-quest not found / cycle / depth exceeded)
        bool hasChildren = src.Children is { Count: > 0 } && depth < 3;

        if (hasChildren)
        {
            if (ImGui.TreeNode(display.ChildrenLabel))
            {
                // Quest reward fallback: still show "Open quest" link
                if (src.Type == "quest_reward" && src.QuestKey != null)
                {
                    var target = _data.GetByStableKey(src.QuestKey);
                    if (target != null)
                    {
                        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
                        if (ImGui.Selectable(display.OpenQuestLabel!))
                        {
                            _state.SelectQuest(target);
                        }
                        ImGui.PopStyleColor();
                    }
                }

                foreach (var child in src.Children!)
                    DrawSource(child, quest, step, visited, depth + 1);
                ImGui.TreePop();
            }
        }
        else if (display.SourceId is string sourceId)
        {
            // Navigable source: highlight when in the active source set.
            // Gold = auto-selected, cyan = manually toggled.
            bool isActive = _nav.IsSourceActive(sourceId);
            if (isActive)
            {
                uint color = _nav.IsManualSourceOverride
                    ? Theme.NavManualOverride
                    : Theme.QuestActive;
                ImGui.PushStyleColor(ImGuiCol.Text, color);
            }

            if (ImGui.Selectable(display.SelectableLabel!))
                _nav.ToggleSource(sourceId, _state.CurrentZone);

            if (isActive)
                ImGui.PopStyleColor();

            if (ImGui.IsItemHovered())
            {
                ImGui.BeginTooltip();
                string action = isActive ? "Remove from" : "Add to";
                if (src.SourceKey != null)
                    ImGui.Text($"{action} navigation: {src.Name}");
                else
                    ImGui.Text($"{action} navigation: {src.Zone ?? src.Scene}");
                ImGui.EndTooltip();
            }
        }
        else
        {
            // Non-navigable source: dimmed text
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.SourceDimmed);
            ImGui.Text(label);
            ImGui.PopStyleColor();
        }
    }

    /// <summary>
    /// For complete_quest steps, render the target quest's steps inline
    /// as an indented sub-tree. Shows an "Open quest" link and the full
    /// step list with NAV buttons, sources, and tips.
    /// </summary>
    private void DrawSubQuestSteps(QuestStep step, QuestEntry quest, HashSet<string> visited)
    {
        if (step.Action != "complete_quest" || step.TargetKey == null)
            return;

        var subQuest = _data.GetByStableKey(step.TargetKey);
        if (subQuest?.Steps == null || subQuest.Steps.Count == 0)
            return;
        if (visited.Count > MaxSubQuestDepth || visited.Contains(subQuest.StableKey))
            return;

        ImGui.Indent();

        // "Open quest" link
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
        if (ImGui.Selectable(_questDisplay[quest].Steps[step].SubQuestLabel!))
            _state.SelectQuest(subQuest);
        ImGui.PopStyleColor();

        // Render the sub-quest's steps inline
        visited.Add(subQuest.StableKey);
        DrawSteps(subQuest, visited);
        visited.Remove(subQuest.StableKey);

        ImGui.Unindent();
    }

    /// <summary>
    /// Render a quest_reward source as an inline sub-quest tree: the TreeNode
    /// header shows the source label, and the body contains the sub-quest's
    /// steps with full treatment (NAV buttons, sources, tips).
    /// </summary>
    private void DrawQuestRewardTree(
        QuestEntry subQuest,
        SourceDisplayCache display,
        HashSet<string> visited
    )
    {
        bool isCompleted = _state.IsCompleted(subQuest);
        var flags = isCompleted ? ImGuiTreeNodeFlags.None : ImGuiTreeNodeFlags.DefaultOpen;

        if (isCompleted)
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestCompleted);

        bool open = ImGui.TreeNodeEx(display.QuestTreeLabel!, flags);

        if (isCompleted)
            ImGui.PopStyleColor();

        if (!open)
            return;

        // "Open quest" link — jump to the full quest detail page
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
        if (ImGui.Selectable(display.OpenQuestLabel!))
        {
            _state.SelectQuest(subQuest);
        }
        ImGui.PopStyleColor();

        // Render the sub-quest's steps inline
        visited.Add(subQuest.StableKey);
        DrawSteps(subQuest, visited);
        visited.Remove(subQuest.StableKey);

        ImGui.TreePop();
    }

    private void DrawTips(QuestStep step, QuestEntry quest)
    {
        if (step.Tips == null || step.Tips.Count == 0)
            return;

        ImGui.Indent();
        if (ImGui.TreeNode(_questDisplay[quest].Steps[step].TipsLabel))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            foreach (var tip in step.Tips)
                ImGui.TextWrapped(tip);
            ImGui.PopStyleColor();
            ImGui.TreePop();
        }
        ImGui.Unindent();
    }

    // ── Rewards ─────────────────────────────────────────────────────

    private void DrawRewards(QuestEntry quest)
    {
        var r = quest.Rewards;
        if (r == null)
            return;
        if (!HasAnyRewards(r))
            return;

        // Expanded by default — rewards are primary motivation
        if (!ImGui.CollapsingHeader("Rewards", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        ImGui.Indent();

        foreach (var line in _rewardLines)
        {
            if (line.Secondary)
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text(line.Text);
            if (line.Secondary)
                ImGui.PopStyleColor();
        }

        ImGui.Unindent();
    }

    private static bool HasAnyRewards(RewardInfo r) =>
        r.XP > 0
        || r.Gold > 0
        || r.ItemName != null
        || r.VendorUnlock != null
        || r.UnlockedZoneLines is { Count: > 0 }
        || r.UnlockedCharacters is { Count: > 0 }
        || r.NextQuestName != null
        || r.FactionEffects is { Count: > 0 }
        || r.AlsoCompletes is { Count: > 0 };

    // ── Prerequisites ───────────────────────────────────────────────

    private void DrawPrerequisites(QuestEntry quest)
    {
        // Prerequisites already visible in the step tree are filtered at
        // cache rebuild (quest_reward sources and complete_quest targets).
        var filtered = _prerequisites;
        if (filtered.Count == 0)
            return;

        // Auto-expand when any prerequisite is incomplete
        bool anyIncomplete = false;
        foreach (var p in filtered)
        {
            if (!IsPrerequisiteCompleted(p.Prerequisite))
            {
                anyIncomplete = true;
                break;
            }
        }

        var flags = anyIncomplete ? ImGuiTreeNodeFlags.DefaultOpen : ImGuiTreeNodeFlags.None;
        if (!ImGui.CollapsingHeader("Prerequisites", flags))
            return;

        ImGui.Indent();
        foreach (var prereq in filtered)
        {
            bool completed = IsPrerequisiteCompleted(prereq.Prerequisite);
            var color = completed ? Theme.QuestCompleted : Theme.TextPrimary;

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            if (ImGui.Selectable(prereq.Label))
            {
                var target = _data.GetByStableKey(prereq.Prerequisite.QuestKey);
                if (target != null)
                    _state.SelectQuest(target);
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent();
    }

    /// <summary>
    /// Collect quest stable keys that are already visible in the step tree:
    /// complete_quest step targets and quest_reward item sources.
    /// Called once per display-cache rebuild, not during frame rendering.
    /// </summary>
    private static HashSet<string> CollectStepTreeQuestKeys(QuestEntry quest)
    {
        var keys = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        if (quest.Steps != null)
        {
            foreach (var step in quest.Steps)
            {
                if (step.Action == "complete_quest" && step.TargetKey != null)
                    keys.Add(step.TargetKey);
            }
        }
        if (quest.RequiredItems != null)
        {
            foreach (var ri in quest.RequiredItems)
            {
                if (ri.Sources != null)
                    CollectQuestRewardKeys(ri.Sources, keys);
            }
        }
        return keys;
    }

    private static void CollectQuestRewardKeys(List<ItemSource> sources, HashSet<string> keys)
    {
        foreach (var src in sources)
        {
            if (src.Type == "quest_reward" && src.QuestKey != null)
                keys.Add(src.QuestKey);
            if (src.Children != null)
                CollectQuestRewardKeys(src.Children, keys);
        }
    }

    private bool IsPrerequisiteCompleted(Prerequisite prereq)
    {
        var quest = _data.GetByStableKey(prereq.QuestKey);
        return quest != null && _state.IsCompleted(quest);
    }

    // ── Display cache ────────────────────────────────────────────────

    private sealed class QuestDisplayCache
    {
        public int CurrentStepIndex;
        public readonly Dictionary<QuestStep, StepDisplayCache> Steps = new();
    }

    private sealed class StepDisplayCache
    {
        public string Text = "";
        public string NavLabel = "";
        public string TipsLabel = "";
        public string? MoreSourcesLabel;
        public string? SubQuestLabel;
        public bool HasRequiredQuantity;
        public bool Navigable;
        public readonly List<ItemSource> VisibleSources = new();
        public readonly Dictionary<(ItemSource Source, int Depth), SourceDisplayCache> Sources =
            new();
    }

    private sealed class SourceDisplayCache
    {
        public string Label = "";
        public string ChildrenLabel = "";
        public string? SourceId;
        public string? SelectableLabel;
        public string? QuestTreeLabel;
        public string? OpenQuestLabel;
    }

    /// <summary>
    /// Rebuild formatted labels and filtered collections for the selected
    /// quest and all drawable inline sub-quests, including closed trees.
    /// Nothing is retained across a selection or state-version change.
    /// </summary>
    private void RebuildDisplayCache()
    {
        _questDisplay.Clear();
        _visited.Clear();
        _acquisitionLines.Clear();
        _completionLines.Clear();
        _rewardLines.Clear();
        _prerequisites.Clear();
        _stepTreeQuestKeys = null;
        _levelZoneLine = null;

        var quest = _cachedQuestKey == null ? null : _data.GetByRuntimeKey(_cachedQuestKey);
        if (quest == null)
            return;

        CacheHeader(quest);
        CacheRewards(quest.Rewards);
        _stepTreeQuestKeys = CollectStepTreeQuestKeys(quest);
        if (quest.Prerequisites != null)
        {
            foreach (var prereq in quest.Prerequisites)
            {
                if (_stepTreeQuestKeys.Contains(prereq.QuestKey))
                    continue;
                string label =
                    prereq.Item != null ? $"{prereq.QuestName} ({prereq.Item})" : prereq.QuestName;
                _prerequisites.Add((prereq, $"{label}##prereq_{prereq.QuestKey}"));
            }
        }

        // Use the drawing set here too, warming its capacity for every
        // possible expanded path before allocation-free frame rendering.
        _visited.Add(quest.StableKey);
        CacheStepTree(quest, _visited);
        _visited.Clear();
    }

    private void CacheHeader(QuestEntry quest)
    {
        int? level = quest.LevelEstimate?.Recommended;
        string? zone = quest.ZoneContext;
        bool repeatable = quest.Flags is { Repeatable: true };
        if (level != null || zone != null || repeatable)
        {
            string meta = level != null ? $"Lv {level}" : "";
            if (zone != null)
            {
                if (meta.Length > 0)
                    meta += "  \u00b7  ";
                meta += zone;
            }
            if (repeatable)
            {
                if (meta.Length > 0)
                    meta += "  \u00b7  ";
                meta += "Repeatable";
            }
            _levelZoneLine = meta;
        }

        if (quest.Acquisition != null)
        {
            foreach (var acq in quest.Acquisition)
            {
                string? line = acq.Method switch
                {
                    "dialog" when acq.SourceName != null => $"Given by: {acq.SourceName}",
                    "item_read" when acq.SourceName != null => $"Read: {acq.SourceName}",
                    "zone_entry" when acq.SourceName != null => $"Enter: {acq.SourceName}",
                    "quest_chain" when acq.SourceName != null => $"Chain from: {acq.SourceName}",
                    _ => acq.SourceName != null ? $"From: {acq.SourceName}" : null,
                };
                if (line == null)
                    continue;
                if (acq.ZoneName != null && acq.Method == "dialog")
                    line += $" ({acq.ZoneName})";
                _acquisitionLines.Add(line);
            }
        }

        if (quest.Completion != null)
        {
            foreach (var comp in quest.Completion)
            {
                string? line = comp.Method switch
                {
                    "item_turnin" or "dialog" when comp.SourceName != null =>
                        $"Turn in to: {comp.SourceName}",
                    "zone" when comp.SourceName != null => $"Complete at: {comp.SourceName}",
                    _ when comp.SourceName != null => $"Complete: {comp.SourceName}",
                    _ => null,
                };
                if (line == null)
                    continue;
                if (comp.ZoneName != null && comp.Method is "item_turnin" or "dialog")
                    line += $" ({comp.ZoneName})";
                _completionLines.Add(line);
            }
        }
    }

    private void CacheRewards(RewardInfo? r)
    {
        if (r == null)
            return;
        if (r.XP > 0)
            _rewardLines.Add(($"{r.XP} XP", false));
        if (r.Gold > 0)
            _rewardLines.Add(($"{r.Gold} Gold", false));
        if (r.ItemName != null)
            _rewardLines.Add((r.ItemName, false));

        // Vendor item unlock
        if (r.VendorUnlock != null)
            _rewardLines.Add(
                ($"Unlocks {r.VendorUnlock.ItemName} at {r.VendorUnlock.VendorName}", false)
            );

        // Zone line unlocks
        if (r.UnlockedZoneLines != null)
        {
            foreach (var zl in r.UnlockedZoneLines)
            {
                string text = $"Opens path from {zl.FromZone} to {zl.ToZone}";
                if (zl.CoRequirements is { Count: > 0 })
                    text += $" (also requires {string.Join(", ", zl.CoRequirements)})";
                _rewardLines.Add((text, false));
            }
        }

        // Character spawn unlocks
        if (r.UnlockedCharacters != null)
        {
            foreach (var ch in r.UnlockedCharacters)
            {
                string text =
                    ch.Zone != null ? $"Enables {ch.Name} in {ch.Zone}" : $"Enables {ch.Name}";
                _rewardLines.Add((text, false));
            }
        }

        // Next quest in chain
        if (r.NextQuestName != null)
            _rewardLines.Add(($"Next: {r.NextQuestName}", true));
        if (r.FactionEffects != null)
        {
            foreach (var fe in r.FactionEffects)
            {
                string sign = fe.Amount >= 0 ? "+" : "";
                _rewardLines.Add(($"{fe.FactionName}: {sign}{fe.Amount}", false));
            }
        }
        if (r.AlsoCompletes is { Count: > 0 })
            _rewardLines.Add(($"Also completes: {string.Join(", ", r.AlsoCompletes)}", true));
    }

    private void CacheStepTree(QuestEntry quest, HashSet<string> visited)
    {
        if (!_questDisplay.TryGetValue(quest, out var display))
        {
            display = new QuestDisplayCache
            {
                CurrentStepIndex = StepProgress.GetCurrentStepIndex(quest, _state, _data),
            };
            _questDisplay.Add(quest, display);
            if (quest.Steps != null)
            {
                foreach (var step in quest.Steps)
                    display.Steps.Add(step, CacheStep(quest, step));
            }
        }
        if (quest.Steps == null)
            return;

        // Traverse each drawable path even for already cached quests:
        // cycle/depth fallbacks depend on the current ancestor set.
        foreach (var step in quest.Steps)
        {
            foreach (var src in display.Steps[step].VisibleSources)
                CacheSourceQuestTree(src, visited);

            if (step.Action == "complete_quest" && step.TargetKey != null)
                CacheInlineQuest(_data.GetByStableKey(step.TargetKey), visited);
        }
    }

    private void CacheInlineQuest(QuestEntry? quest, HashSet<string> visited)
    {
        if (
            quest?.Steps is not { Count: > 0 }
            || visited.Count > MaxSubQuestDepth
            || visited.Contains(quest.StableKey)
        )
            return;
        visited.Add(quest.StableKey);
        CacheStepTree(quest, visited);
        visited.Remove(quest.StableKey);
    }

    private void CacheSourceQuestTree(ItemSource src, HashSet<string> visited, int depth = 0)
    {
        if (!IsSourceAvailable(src))
            return;
        if (src.Type == "quest_reward" && src.QuestKey != null)
        {
            var subQuest = _data.GetByStableKey(src.QuestKey);
            if (
                subQuest?.Steps is { Count: > 0 }
                && visited.Count <= MaxSubQuestDepth
                && !visited.Contains(subQuest.StableKey)
            )
            {
                CacheInlineQuest(subQuest, visited);
                return;
            }
        }
        if (src.Children != null && depth < 3)
        {
            foreach (var child in src.Children)
                CacheSourceQuestTree(child, visited, depth + 1);
        }
    }

    private StepDisplayCache CacheStep(QuestEntry quest, QuestStep step)
    {
        var display = new StepDisplayCache
        {
            Text = $"{step.Order}. {step.Description}",
            NavLabel = $"[NAV]##{step.Order}",
            TipsLabel = $"Tips##{step.Order}",
        };

        // Collect steps: have/need counts change only with the state version.
        if (StepCountPolicy.ShowsInventoryCount(step))
        {
            int have = _state.CountItem(step.TargetKey!);
            display.Text += $" ({have}/{step.Quantity})";
            display.HasRequiredQuantity = have >= step.Quantity!.Value;
        }

        // Step suffix: zone (for non-collect) and level, dot-separated.
        if (step.LevelEstimate?.Recommended is int stepLvl)
        {
            // Non-collect steps show zone since there's no source list below.
            if (
                (step.Action is not "collect" and not "obtain" and not "read")
                && step.LevelEstimate.Factors is { Count: > 0 }
            )
                display.Text += $"  \u00b7  {step.LevelEstimate.Factors[0].Name}";
            display.Text += $"  \u00b7  Lv {stepLvl}";
        }
        else if (
            (step.Action is not "collect" and not "obtain" and not "read")
            && step.LevelEstimate?.Factors is { Count: > 0 }
        )
        {
            // Zone without level
            display.Text += $"  \u00b7  {step.LevelEstimate.Factors[0].Name}";
        }

        var item = FindRequiredItem(quest, step);
        if (step.TargetType == "item" && item?.Sources != null)
        {
            foreach (var source in item.Sources)
            {
                if (HasNavigableSource(source))
                {
                    display.Navigable = true;
                    break;
                }
            }
        }
        else if (step.TargetType == "character")
            display.Navigable =
                step.TargetKey != null && _data.CharacterSpawns.ContainsKey(step.TargetKey);
        else if (step.TargetType == "zone")
            display.Navigable = step.ZoneName != null || step.TargetKey != null;

        if (
            (step.Action is "collect" or "obtain" or "read")
            && step.TargetName != null
            && item?.Sources != null
        )
        {
            foreach (var source in item.Sources)
            {
                if (!IsSourceAvailable(source))
                    continue;
                display.VisibleSources.Add(source);
                CacheSourceLabels(source, step, display);
            }
        }
        if (display.VisibleSources.Count > 4)
        {
            int remaining = display.VisibleSources.Count - 4;
            int minLv = display.VisibleSources[4].Level ?? 0;
            int maxLv = display.VisibleSources[^1].Level ?? minLv;
            string range = minLv == maxLv ? $"Lv {minLv}" : $"Lv {minLv}-{maxLv}";
            display.MoreSourcesLabel = $"{remaining} more sources ({range})##{step.Order}";
        }

        if (step.Action == "complete_quest" && step.TargetKey != null)
        {
            var subQuest = _data.GetByStableKey(step.TargetKey);
            if (subQuest != null)
                display.SubQuestLabel =
                    $"Open quest: {subQuest.DisplayName}##cq_{step.Order}_{step.TargetKey}";
        }
        return display;
    }

    private void CacheSourceLabels(
        ItemSource src,
        QuestStep step,
        StepDisplayCache stepDisplay,
        int depth = 0
    )
    {
        if (stepDisplay.Sources.ContainsKey((src, depth)))
            return;
        string label = src.Type switch
        {
            "drop" => $"Drops from: {src.Name}",
            "vendor" when !string.IsNullOrWhiteSpace(src.Instruction) =>
                $"{src.Instruction}  ·  {src.Name}",
            "vendor" => $"Buy from: {src.Name}",
            "dialog_give" => $"Given by: {src.Name}",
            "fishing" => "Fishing",
            "mining" => "Mining",
            "pickup" => "Found in world",
            "crafting" => $"Crafted from: {src.Name}",
            "quest_reward" => $"Quest reward: {src.Name}",
            "ingredient" => $"Ingredient: {src.Name}"
                + (src.NodeCount is int qty ? $" x{qty}" : ""),
            "item_use" => $"Use: {src.Name}",
            _ => src.Name ?? src.Type,
        };
        if (src.Zone != null)
            label += $"  \u00b7  {src.Zone}";
        if (src.Level is int lv)
            label += $"  \u00b7  Lv {lv}";

        var display = new SourceDisplayCache
        {
            Label = label,
            ChildrenLabel = $"{label}##src_{step.Order}_{depth}_{src.Type}_{src.Name}",
            SourceId = src.MakeSourceId(),
        };
        if (display.SourceId != null)
            display.SelectableLabel = $"{label}##src_{step.Order}_{display.SourceId}";
        if (src.Type == "quest_reward" && src.QuestKey != null)
        {
            display.QuestTreeLabel = $"{label}##sqt_{step.Order}_{src.QuestKey}";
            var target = _data.GetByStableKey(src.QuestKey);
            if (target != null)
                display.OpenQuestLabel =
                    $"Open quest: {target.DisplayName}##goto_{step.Order}_{src.QuestKey}";
        }
        stepDisplay.Sources.Add((src, depth), display);
        if (src.Children != null && depth < 3)
        {
            foreach (var child in src.Children)
                CacheSourceLabels(child, step, stepDisplay, depth + 1);
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────

    /// <summary>
    /// Find the RequiredItemInfo matching a collect/read step's target name.
    /// </summary>
    private static RequiredItemInfo? FindRequiredItem(QuestEntry quest, QuestStep step)
    {
        if (quest.RequiredItems != null)
        {
            foreach (var item in quest.RequiredItems)
            {
                if (
                    string.Equals(
                        item.ItemName,
                        step.TargetName,
                        StringComparison.OrdinalIgnoreCase
                    )
                )
                    return item;
            }
        }
        return null;
    }

    private bool IsSourceAvailable(ItemSource source)
    {
        if (source.RequiredQuestDBNames != null)
        {
            foreach (var dbName in source.RequiredQuestDBNames)
            {
                if (!_state.IsGameQuestCompleted(dbName))
                    return false;
            }
        }
        return true;
    }

    private bool HasNavigableSource(ItemSource s)
    {
        if (!IsSourceAvailable(s))
            return false;
        if (s.Scene != null)
            return true;
        if (s.SourceKey != null && _data.CharacterSpawns.ContainsKey(s.SourceKey))
            return true;
        if (s.Children != null)
        {
            foreach (var child in s.Children)
            {
                if (HasNavigableSource(child))
                    return true;
            }
        }
        return false;
    }
}
