using AdventureGuide.Data;
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

    public QuestDetailPanel(GuideData data, QuestStateTracker state)
    {
        _data = data;
        _state = state;
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
                    "dialog" => $"Given by: {acq.SourceName}",
                    "item_read" => $"Read: {acq.SourceName}",
                    "zone_entry" => $"Enter: {acq.ZoneName}",
                    "quest_chain" => $"Chain from: {acq.SourceName}",
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
                if (comp.SourceName == null) continue;
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                string turnIn = comp.Method switch
                {
                    "item_turnin" or "dialog" => $"Turn in to: {comp.SourceName}",
                    "zone" => $"Complete at: {comp.ZoneName}",
                    _ => $"Complete: {comp.SourceName}",
                };
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
                string marker = isDriving ? " \u25c4" : "";
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

        int currentStepIndex = DetermineCurrentStep(quest);

        ImGui.Indent(Theme.IndentWidth);
        for (int i = 0; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];

            if (i < currentStepIndex)
                DrawStep(step, StepState.Completed);
            else if (i == currentStepIndex)
                DrawStep(step, StepState.Current);
            else
                DrawStep(step, StepState.Future);
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private enum StepState { Completed, Current, Future }

    private void DrawStep(QuestStep step, StepState state)
    {
        uint color = state switch
        {
            StepState.Completed => Theme.QuestCompleted,
            StepState.Current => Theme.QuestActive,
            _ => Theme.TextPrimary,
        };
        string prefix = state switch
        {
            StepState.Completed => "\u2713",
            StepState.Current => ">>",
            _ => "\u25cb",
        };

        string text = $"{prefix} {step.Order}. {step.Description}";

        // Collect steps: show have/need count
        if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
        {
            int have = _state.CountItemInInventory(step.TargetName);
            text += $" ({have}/{step.Quantity})";
        }

        // Step-level suffix: for collect steps just the level (sources shown below),
        // for non-collect steps include the zone name since there's no source list
        if (step.LevelEstimate?.Recommended is int stepLvl)
        {
            if (step.Action is "collect" or "read")
                text += $"  \u00b7  Lv {stepLvl}";
            else if (step.LevelEstimate.Factors is { Count: > 0 })
                text += $"  \u00b7  Lv {stepLvl} ({step.LevelEstimate.Factors[0].Name})";
            else
                text += $"  \u00b7  Lv {stepLvl}";
        }

        ImGui.PushStyleColor(ImGuiCol.Text, color);
        ImGui.Text(text);
        ImGui.PopStyleColor();

        // Drop/vendor sources and tips for collect steps
        DrawStepSources(step);
    }

    /// <summary>
    /// Show obtainability sources sorted by level (easiest first), with levels
    /// annotated inline. Collapses beyond 4 sources behind a TreeNode.
    /// </summary>
    private void DrawStepSources(QuestStep step)
    {
        if (step.Action is not "collect" and not "read" || step.TargetName == null)
        {
            DrawTips(step);
            return;
        }

        var quest = _data.GetByDBName(_state.SelectedQuestDBName!);
        var item = quest?.RequiredItems?.Find(ri =>
            string.Equals(ri.ItemName, step.TargetName, StringComparison.OrdinalIgnoreCase));

        if (item == null)
        {
            DrawTips(step);
            return;
        }

        // Build factor lookup: "source:name" -> level
        var levelByKey = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        if (step.LevelEstimate?.Factors != null)
            foreach (var f in step.LevelEstimate.Factors)
                levelByKey[$"{f.Source}:{f.Name}"] = f.Level;

        // Collect all sources into a unified list with labels and levels
        var sources = new List<(string label, int? level)>();

        if (item.DropSources != null)
            foreach (var ds in item.DropSources)
            {
                var zone = ds.ZoneName != null ? $" ({ds.ZoneName})" : "";
                levelByKey.TryGetValue($"enemy_level:{ds.CharacterName}", out int lv);
                sources.Add(($"Drops from: {ds.CharacterName}{zone}", lv > 0 ? lv : null));
            }

        if (item.VendorSources != null)
            foreach (var vs in item.VendorSources)
            {
                var zone = vs.ZoneName != null ? $" ({vs.ZoneName})" : "";
                levelByKey.TryGetValue($"vendor_zone:{vs.CharacterName} ({vs.ZoneName})", out int lv);
                sources.Add(($"Sold by: {vs.CharacterName}{zone}", lv > 0 ? lv : null));
            }

        // Fishing/mining/bag: deduplicate by zone (individual nodes aren't useful)
        var seenZones = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        if (item.FishingSources is { Count: > 0 })
            foreach (var fs in item.FishingSources)
            {
                string key = $"fishing:{fs.ZoneName}";
                if (!seenZones.Add(key)) continue;
                var zone = fs.ZoneName != null ? $" ({fs.ZoneName})" : "";
                levelByKey.TryGetValue($"fishing_zone:{fs.ZoneName}", out int lv);
                sources.Add(($"Fishing{zone}", lv > 0 ? lv : null));
            }

        if (item.MiningSources is { Count: > 0 })
            foreach (var ms in item.MiningSources)
            {
                string key = $"mining:{ms.ZoneName}";
                if (!seenZones.Add(key)) continue;
                var zone = ms.ZoneName != null ? $" ({ms.ZoneName})" : "";
                levelByKey.TryGetValue($"mining_zone:{ms.ZoneName}", out int lv);
                sources.Add(($"Mining{zone}", lv > 0 ? lv : null));
            }

        if (item.BagSources is { Count: > 0 })
            foreach (var bs in item.BagSources)
            {
                string key = $"bag:{bs.ZoneName}";
                if (!seenZones.Add(key)) continue;
                var zone = bs.ZoneName != null ? $" ({bs.ZoneName})" : "";
                levelByKey.TryGetValue($"pickup_zone:{bs.ZoneName}", out int lv);
                sources.Add(($"Found in world{zone}", lv > 0 ? lv : null));
            }

        if (item.CraftingSources is { Count: > 0 })
            foreach (var cs in item.CraftingSources)
                sources.Add(($"Crafted from: {cs.RecipeItemName}", null));

        if (item.QuestRewardSources is { Count: > 0 })
            foreach (var qr in item.QuestRewardSources)
                sources.Add(($"Quest reward: {qr.QuestName}", null));

        if (sources.Count == 0)
        {
            DrawTips(step);
            return;
        }

        // Sort by level ascending (null-level sources at end)
        sources.Sort((a, b) =>
        {
            if (a.level == null && b.level == null) return 0;
            if (a.level == null) return 1;
            if (b.level == null) return -1;
            return a.level.Value.CompareTo(b.level.Value);
        });

        ImGui.Indent(Theme.IndentWidth);
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);

        const int maxVisible = 4;
        int visible = Math.Min(sources.Count, maxVisible);

        for (int i = 0; i < visible; i++)
        {
            var (label, level) = sources[i];
            string line = level.HasValue ? $"{label}  \u00b7  Lv {level}" : label;
            ImGui.Text(line);
        }

        // Collapse remaining behind a TreeNode
        if (sources.Count > maxVisible)
        {
            int remaining = sources.Count - maxVisible;
            int minLv = sources[maxVisible].level ?? 0;
            int maxLv = sources[^1].level ?? minLv;
            string range = minLv == maxLv ? $"Lv {minLv}" : $"Lv {minLv}-{maxLv}";
            if (ImGui.TreeNode($"{remaining} more sources ({range})##{step.Order}"))
            {
                for (int i = maxVisible; i < sources.Count; i++)
                {
                    var (label, level) = sources[i];
                    string line = level.HasValue ? $"{label}  \u00b7  Lv {level}" : label;
                    ImGui.Text(line);
                }
                ImGui.TreePop();
            }
        }

        ImGui.PopStyleColor();
        ImGui.Unindent(Theme.IndentWidth);

        DrawTips(step);
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

    /// <summary>
    /// Walk steps to find the first incomplete one. Conservative approach:
    /// only advance past steps we can verify (collect with item count).
    /// Non-verifiable steps (talk, kill, shout, turn_in) stop the pointer.
    /// Exception: step 0 is auto-completed for active quests when it matches
    /// the acquisition action (e.g. talk to quest giver, read trigger item).
    /// </summary>
    private int DetermineCurrentStep(QuestEntry quest)
    {
        if (_state.IsCompleted(quest.DBName))
            return quest.Steps!.Count;

        if (!_state.IsActive(quest.DBName))
            return 0;

        // Step 0 is the acquisition action for most quests (talk to giver,
        // read trigger item, travel to trigger zone). If active, the player
        // already performed it to accept the quest — skip it.
        int start = IsAcquisitionStep(quest, quest.Steps![0]) ? 1 : 0;

        for (int i = start; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
            {
                int have = _state.CountItemInInventory(step.TargetName);
                if (have < step.Quantity.Value)
                    return i;
                // have >= need: this collect step is done, continue to next
            }
            else
            {
                // Can't verify: treat as current (conservative)
                return i;
            }
        }

        // All verifiable steps done — point to last step
        return quest.Steps.Count - 1;
    }

    /// <summary>
    /// Returns true when step 0 represents the quest acquisition action
    /// itself (talk to quest giver, read trigger item, enter trigger zone).
    /// Matched by comparing the step action/target against acquisition sources.
    /// </summary>
    private static bool IsAcquisitionStep(QuestEntry quest, QuestStep step)
    {
        if (quest.Acquisition == null || quest.Acquisition.Count == 0)
            return false;

        foreach (var acq in quest.Acquisition)
        {
            if (step.Action == "talk" && acq.Method == "dialog"
                && string.Equals(step.TargetName, acq.SourceName, StringComparison.OrdinalIgnoreCase))
                return true;

            if (step.Action == "read" && acq.Method == "item_read"
                && string.Equals(step.TargetName, acq.SourceName, StringComparison.OrdinalIgnoreCase))
                return true;

            if (step.Action == "travel" && acq.Method == "zone_entry")
                return true;
        }

        return false;
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
        foreach (var prereqName in quest.Prerequisites)
        {
            bool completed = IsPrerequisiteCompleted(prereqName);
            var color = completed ? Theme.QuestCompleted : Theme.TextPrimary;
            var prefix = completed ? "\u2713 " : "\u25cb ";

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            if (ImGui.Selectable($"{prefix}{prereqName}##prereq"))
            {
                // Navigate to prerequisite quest
                foreach (var entry in _data.All)
                {
                    if (string.Equals(entry.DisplayName, prereqName, StringComparison.OrdinalIgnoreCase))
                    {
                        _state.SelectedQuestDBName = entry.DBName;
                        break;
                    }
                }
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private bool IsPrerequisiteCompleted(string prereqName)
    {
        foreach (var entry in _data.All)
        {
            if (string.Equals(entry.DisplayName, prereqName, StringComparison.OrdinalIgnoreCase))
                return _state.IsCompleted(entry.DBName);
        }
        return false;
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
                    _state.SelectedQuestDBName = linkedQuest.DBName;
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }
}
