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

    /// <summary>Max sub-quest nesting depth to prevent runaway recursion.</summary>
    private const int MaxSubQuestDepth = 5;

    public QuestDetailPanel(GuideData data, QuestStateTracker state, NavigationController nav,
        TrackerState tracker, GuideConfig config)
    {
        _data = data;
        _state = state;
        _nav = nav;
        _tracker = tracker;
        _config = config;
    }

    public void Draw()
    {
        if (_state.SelectedQuestDBName == null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.TextWrapped("Select a quest from the list.");
            ImGui.PopStyleColor();
            return;
        }

        var quest = _data.GetByDBName(_state.SelectedQuestDBName);
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
        DrawChain(quest);
    }

    // ── Header ──────────────────────────────────────────────────────

    private void DrawHeader(QuestEntry quest)
    {
        // Quest name in header color
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();

        // Track/Untrack button (only when tracker is enabled; not for completed quests)
        if (_tracker.Enabled && !_state.IsCompleted(quest.DBName))
        {
            bool tracked = _tracker.IsTracked(quest.DBName);
            if (tracked)
                ImGui.PushStyleColor(ImGuiCol.Button, Theme.Accent);
            if (ImGui.SmallButton(tracked ? "[Untrack]" : "[Track]"))
            {
                if (tracked)
                    _tracker.Untrack(quest.DBName);
                else
                    _tracker.Track(quest.DBName);
            }
            if (tracked)
                ImGui.PopStyleColor();
        }

        // Level + zone on one line (replaces separate "Zone:" line)
        DrawLevelZoneLine(quest);

        // All acquisition sources (not just dialog)
        if (quest.Acquisition != null)
        {
            foreach (var acq in quest.Acquisition)
            {
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                string? line = acq.Method switch
                {
                    "dialog" when acq.SourceName != null => $"Given by: {acq.SourceName}",
                    "item_read" when acq.SourceName != null => $"Read: {acq.SourceName}",
                    "zone_entry" when acq.SourceName != null => $"Enter: {acq.SourceName}",
                    "quest_chain" when acq.SourceName != null => $"Chain from: {acq.SourceName}",
                    _ => acq.SourceName != null ? $"From: {acq.SourceName}" : null,
                };
                if (line != null)
                {
                    if (acq.ZoneName != null && acq.Method == "dialog")
                        line += $" ({acq.ZoneName})";
                    ImGui.Text(line);
                }
                ImGui.PopStyleColor();
            }
        }

        // Turn-in location
        if (quest.Completion != null)
        {
            foreach (var comp in quest.Completion)
            {
                if (comp.SourceName == null && comp.ZoneName == null) continue;
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                string? turnIn = comp.Method switch
                {
                    "item_turnin" or "dialog" when comp.SourceName != null => $"Turn in to: {comp.SourceName}",
                    "zone" when comp.SourceName != null => $"Complete at: {comp.SourceName}",
                    _ when comp.SourceName != null => $"Complete: {comp.SourceName}",
                    _ => null,
                };
                if (turnIn == null) { ImGui.PopStyleColor(); continue; }
                if (comp.ZoneName != null && comp.Method is "item_turnin" or "dialog")
                    turnIn += $" ({comp.ZoneName})";
                ImGui.Text(turnIn);
                ImGui.PopStyleColor();
            }
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

    private static void DrawLevelZoneLine(QuestEntry quest)
    {
        int? level = quest.LevelEstimate?.Recommended;
        string? zone = quest.ZoneContext;

        if (level == null && zone == null)
            return;

        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        string meta = "";
        if (level != null)
            meta = $"Lv {level}";
        if (level != null && zone != null)
            meta += "  \u00b7  ";
        if (zone != null)
            meta += zone;

        ImGui.Text(meta);

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
                string lvlStr = stepLvl.HasValue ? $"Lv {stepLvl,2}" : "    ";
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
        if (quest.Steps == null || quest.Steps.Count == 0)
            return;

        if (!ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        var visited = new HashSet<string> { quest.StableKey };
        ImGui.Indent(Theme.IndentWidth);
        DrawSteps(quest, visited);
        ImGui.Unindent(Theme.IndentWidth);
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

        ImGui.PushID(quest.DBName);

        int currentStepIndex = StepProgress.GetCurrentStepIndex(quest, _state);
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

    private enum StepState { Completed, Current, Future }

    private void DrawStep(QuestStep step, StepState state, QuestEntry quest, HashSet<string> visited)
    {
        uint color = state switch
        {
            StepState.Completed => Theme.QuestCompleted,
            StepState.Current => Theme.QuestActive,
            _ => Theme.TextPrimary,
        };
        string text = $"{step.Order}. {step.Description}";

        // Collect steps: show have/need count
        if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
        {
            int have = _state.CountItemInInventory(step.TargetName);
            text += $" ({have}/{step.Quantity})";
        }

        // Step suffix: zone (for non-collect) and level, dot-separated
        if (step.LevelEstimate?.Recommended is int stepLvl)
        {
            // Non-collect steps show zone since there's no source list below
            if (step.Action is not "collect" and not "read"
                && step.LevelEstimate.Factors is { Count: > 0 })
                text += $"  \u00b7  {step.LevelEstimate.Factors[0].Name}";
            text += $"  \u00b7  Lv {stepLvl}";
        }
        else if (step.Action is not "collect" and not "read"
                 && step.LevelEstimate?.Factors is { Count: > 0 })
        {
            // Zone without level
            text += $"  \u00b7  {step.LevelEstimate.Factors[0].Name}";
        }

        // [NAV] button first (fixed width), then step text
        DrawNavButton(step, quest);

        ImGui.PushStyleColor(ImGuiCol.Text, color);
        ImGui.Text(text);
        ImGui.PopStyleColor();

        // Drop/vendor sources and tips for collect steps
        DrawStepSources(step, quest, visited);

        // Show alternative zone lines when cross-zone navigating this step
        if (_nav.IsNavigating(quest.DBName, step.Order))
        {
            var alternatives = _nav.GetAlternativeZoneLines(_state.CurrentZone);
            if (alternatives.Count > 1)
                DrawZoneLineAlternatives(alternatives, step);
        }
    }

    private bool IsNavigationEnabled =>
        _config.ShowArrow.Value || _config.ShowGroundPath.Value;

    private void DrawNavButton(QuestStep step, QuestEntry quest)
    {
        if (!IsNavigationEnabled) return;
        if (step.TargetKey == null) return;

        // Item steps are only navigable if at least one source has spawn data
        bool navigable = true;
        if (step.TargetType == "item")
        {
            var item = FindRequiredItem(quest, step);
            navigable = item?.Sources?.Exists(HasNavigableSource) == true;
        }

        bool isActive = _nav.IsNavigating(quest.DBName, step.Order);

        if (!navigable)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.PushStyleVar(ImGuiStyleVar.Alpha, 0.4f);
            ImGui.SmallButton($"[NAV]##{step.Order}");
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

        if (ImGui.SmallButton($"[NAV]##{step.Order}"))
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
    /// </summary>
    private void DrawStepSources(QuestStep step, QuestEntry quest, HashSet<string> visited)
    {
        if (step.Action is not "collect" and not "read" || step.TargetName == null)
        {
            DrawTips(step);
            return;
        }

        var item = FindRequiredItem(quest, step);

        if (item?.Sources == null || item.Sources.Count == 0)
        {
            DrawTips(step);
            return;
        }

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        const int maxVisible = 4;
        int visible = Math.Min(item.Sources.Count, maxVisible);

        for (int i = 0; i < visible; i++)
            DrawSource(item.Sources[i], quest, step, visited);

        if (item.Sources.Count > maxVisible)
        {
            int remaining = item.Sources.Count - maxVisible;
            int minLv = item.Sources[maxVisible].Level ?? 0;
            int maxLv = item.Sources[^1].Level ?? minLv;
            string range = minLv == maxLv ? $"Lv {minLv}" : $"Lv {minLv}-{maxLv}";
            if (ImGui.TreeNode($"{remaining} more sources ({range})##{step.Order}"))
            {
                for (int i = maxVisible; i < item.Sources.Count; i++)
                    DrawSource(item.Sources[i], quest, step, visited);
                ImGui.TreePop();
            }
        }

        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);

        DrawTips(step);
    }

    private void DrawZoneLineAlternatives(
        List<(ZoneLineEntry line, float distance, bool isSelected, bool isAccessible)> alternatives,
        QuestStep step)
    {
        ImGui.Indent(Theme.IndentWidth);
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
                                if (_state.IsCompleted(questDBName))
                                    continue;
                                var entry = _data.GetByDBName(questDBName);
                                if (entry == null) continue;
                                ImGui.Indent(Theme.IndentWidth);
                                if (ImGui.Selectable($"Requires: \"{entry.DisplayName}\"##rq_{step.Order}_{i}_{questDBName}"))
                                    _state.SelectQuest(entry.DBName);
                                ImGui.Unindent(Theme.IndentWidth);
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
        ImGui.Unindent(Theme.IndentWidth);
    }

    private void DrawSource(ItemSource src, QuestEntry quest, QuestStep step, HashSet<string> visited, int depth = 0)
    {
        // Consistent format: {what}  ·  {where}  ·  Lv {N}
        string what = src.Type switch
        {
            "drop" => $"Drops from: {src.Name}",
            "vendor" => $"Sold by: {src.Name}",
            "dialog_give" => $"Given by: {src.Name}",
            "fishing" => "Fishing",
            "mining" => "Mining",
            "pickup" => "Found in world",
            "crafting" => $"Crafted from: {src.Name}",
            "quest_reward" => $"Quest reward: {src.Name}",
            "ingredient" => $"Ingredient: {src.Name}" + (src.NodeCount is int qty ? $" x{qty}" : ""),
            _ => src.Name ?? src.Type,
        };
        string label = what;
        if (src.Zone != null)
            label += $"  \u00b7  {src.Zone}";
        if (src.Level is int lv)
            label += $"  \u00b7  Lv {lv}";

        // Quest reward with a resolvable sub-quest: render its steps inline
        if (src.Type == "quest_reward" && src.QuestKey != null)
        {
            var subQuest = _data.GetByStableKey(src.QuestKey);
            if (subQuest?.Steps is { Count: > 0 }
                && visited.Count <= MaxSubQuestDepth
                && !visited.Contains(subQuest.StableKey))
            {
                DrawQuestRewardTree(src, subQuest, label, step, visited);
                return;
            }
        }

        // Non-quest-reward children (crafting ingredients, or quest_reward
        // fallback when sub-quest not found / cycle / depth exceeded)
        bool hasChildren = src.Children is { Count: > 0 } && depth < 3;

        if (hasChildren)
        {
            if (ImGui.TreeNode($"{label}##src_{step.Order}_{depth}_{src.Type}_{src.Name}"))
            {
                // Quest reward fallback: still show "Open quest" link
                if (src.Type == "quest_reward" && src.QuestKey != null)
                {
                    var target = _data.GetByStableKey(src.QuestKey);
                    if (target != null)
                    {
                        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
                        if (ImGui.Selectable($"Open quest: {target.DisplayName}##goto_{step.Order}_{src.QuestKey}"))
                        {
                            _state.SelectQuest(target.DBName);
                        }
                        ImGui.PopStyleColor();
                    }
                }

                foreach (var child in src.Children!)
                    DrawSource(child, quest, step, visited, depth + 1);
                ImGui.TreePop();
            }
        }
        else if (src.MakeSourceId() is string sourceId)
        {
            // Navigable source: Selectable with highlight when actively
            // navigating to this specific source (not just the same step).
            bool isNavTarget = _nav.Target?.SourceId == sourceId;
            if (isNavTarget)
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);

            if (ImGui.Selectable($"{label}##src_{step.Order}_{sourceId}"))
            {
                if (src.SourceKey != null)
                {
                    _nav.NavigateToSource(src.SourceKey, src.Name ?? src.SourceKey,
                        src.Scene, quest.DBName, step.Order, _state.CurrentZone);
                }
                else if (src.Scene != null)
                {
                    _nav.NavigateToZone(src.Scene, src.Zone ?? src.Scene, sourceId,
                        quest.DBName, step.Order, _state.CurrentZone);
                }
            }

            if (isNavTarget)
                ImGui.PopStyleColor();

            if (ImGui.IsItemHovered())
            {
                ImGui.BeginTooltip();
                if (src.SourceKey != null)
                    ImGui.Text($"Navigate to {src.Name}");
                else if (string.Equals(src.Scene, _state.CurrentZone,
                    System.StringComparison.OrdinalIgnoreCase))
                    ImGui.Text($"You are in {src.Zone ?? src.Scene}");
                else
                    ImGui.Text($"Navigate to {src.Zone ?? src.Scene}");
                ImGui.EndTooltip();
            }
        }
        else
        {
            ImGui.Text(label);
        }
    }

    /// <summary>
    /// Render a quest_reward source as an inline sub-quest tree: the TreeNode
    /// header shows the source label, and the body contains the sub-quest's
    /// steps with full treatment (NAV buttons, sources, tips).
    /// </summary>
    private void DrawQuestRewardTree(
        ItemSource src, QuestEntry subQuest, string label, QuestStep parentStep,
        HashSet<string> visited)
    {
        bool isCompleted = _state.IsCompleted(subQuest.DBName);
        var flags = isCompleted ? ImGuiTreeNodeFlags.None : ImGuiTreeNodeFlags.DefaultOpen;

        if (isCompleted)
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestCompleted);

        bool open = ImGui.TreeNodeEx(
            $"{label}##sqt_{parentStep.Order}_{src.QuestKey}",
            flags);

        if (isCompleted)
            ImGui.PopStyleColor();

        if (!open)
            return;

        // "Open quest" link — jump to the full quest detail page
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
        if (ImGui.Selectable($"Open quest: {subQuest.DisplayName}##goto_{parentStep.Order}_{src.QuestKey}"))
        {
            _state.SelectQuest(subQuest.DBName);
        }
        ImGui.PopStyleColor();

        // Render the sub-quest's steps inline
        visited.Add(subQuest.StableKey);
        DrawSteps(subQuest, visited);
        visited.Remove(subQuest.StableKey);

        ImGui.TreePop();
    }

    private void DrawTips(QuestStep step)
    {
        if (step.Tips == null || step.Tips.Count == 0) return;

        ImGui.Indent(Theme.IndentWidth);
        if (ImGui.TreeNode($"Tips##{step.Order}"))
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            foreach (var tip in step.Tips)
                ImGui.TextWrapped(tip);
            ImGui.PopStyleColor();
            ImGui.TreePop();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    // ── Rewards ─────────────────────────────────────────────────────

    private void DrawRewards(QuestEntry quest)
    {
        var r = quest.Rewards;
        if (r == null) return;
        if (r.XP == 0 && r.Gold == 0 && r.ItemName == null && r.FactionEffects == null)
            return;

        // Expanded by default — rewards are primary motivation
        if (!ImGui.CollapsingHeader("Rewards", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        ImGui.Indent(Theme.IndentWidth);

        if (r.XP > 0)
            ImGui.Text($"{r.XP} XP");
        if (r.Gold > 0)
            ImGui.Text($"{r.Gold} Gold");
        if (r.ItemName != null)
            ImGui.Text(r.ItemName);
        if (r.FactionEffects != null)
        {
            foreach (var fe in r.FactionEffects)
            {
                var sign = fe.Amount >= 0 ? "+" : "";
                ImGui.Text($"{fe.FactionName}: {sign}{fe.Amount}");
            }
        }
        if (r.AlsoCompletes != null && r.AlsoCompletes.Count > 0)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text($"Also completes: {string.Join(", ", r.AlsoCompletes)}");
            ImGui.PopStyleColor();
        }

        ImGui.Unindent(Theme.IndentWidth);
    }

    // ── Prerequisites ───────────────────────────────────────────────

    private void DrawPrerequisites(QuestEntry quest)
    {
        if (quest.Prerequisites == null || quest.Prerequisites.Count == 0)
            return;

        // Auto-expand when any prerequisite is incomplete
        bool anyIncomplete = false;
        foreach (var p in quest.Prerequisites)
        {
            if (!IsPrerequisiteCompleted(p))
            {
                anyIncomplete = true;
                break;
            }
        }

        var flags = anyIncomplete ? ImGuiTreeNodeFlags.DefaultOpen : ImGuiTreeNodeFlags.None;
        if (!ImGui.CollapsingHeader("Prerequisites", flags))
            return;

        ImGui.Indent(Theme.IndentWidth);
        foreach (var prereq in quest.Prerequisites)
        {
            bool completed = IsPrerequisiteCompleted(prereq);
            var color = completed ? Theme.QuestCompleted : Theme.TextPrimary;
            string label = prereq.Item != null
                ? $"{prereq.QuestName} ({prereq.Item})"
                : prereq.QuestName;

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            if (ImGui.Selectable($"{label}##prereq_{prereq.QuestKey}"))
            {
                // Navigate to prerequisite quest via stable key (O(1) lookup)
                var target = _data.GetByStableKey(prereq.QuestKey);
                if (target != null)
                {
                    _state.SelectQuest(target.DBName);
                }
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private bool IsPrerequisiteCompleted(Prerequisite prereq)
    {
        var quest = _data.GetByStableKey(prereq.QuestKey);
        return quest != null && _state.IsCompleted(quest.DBName);
    }

    // ── Chain ────────────────────────────────────────────────────────

    private void DrawChain(QuestEntry quest)
    {
        if (quest.Chain == null || quest.Chain.Count == 0)
            return;

        if (!ImGui.CollapsingHeader("Quest Chain", ImGuiTreeNodeFlags.None))
            return;

        ImGui.Indent(Theme.IndentWidth);
        foreach (var link in quest.Chain)
        {
            string arrow = link.Relationship switch
            {
                "previous" => "<< ",
                "next" => ">> ",
                "completed_by" => "<= ",
                _ => "   "
            };

            bool isCompleted = false;
            var linkedQuest = _data.GetByStableKey(link.QuestStableKey);
            if (linkedQuest != null)
                isCompleted = _state.IsCompleted(linkedQuest.DBName);

            var color = isCompleted ? Theme.QuestCompleted : Theme.TextPrimary;

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            if (ImGui.Selectable($"{arrow}{link.QuestName}##{link.QuestStableKey}"))
            {
                if (linkedQuest != null)
                {
                    _state.SelectQuest(linkedQuest.DBName);
                }
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    // ── Helpers ──────────────────────────────────────────────────────

    /// <summary>
    /// Find the RequiredItemInfo matching a collect/read step's target name.
    /// </summary>
    private static RequiredItemInfo? FindRequiredItem(QuestEntry quest, QuestStep step) =>
        quest.RequiredItems?.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, StringComparison.OrdinalIgnoreCase));

    private static bool HasNavigableSource(ItemSource s) =>
        s.SourceKey != null || s.Scene != null || (s.Children?.Exists(HasNavigableSource) == true);
}
