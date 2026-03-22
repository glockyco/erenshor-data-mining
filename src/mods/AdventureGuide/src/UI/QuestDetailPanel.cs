using System.Numerics;
using AdventureGuide.Data;
using AdventureGuide.State;
using ImGuiNET;

namespace AdventureGuide.UI;

/// <summary>
/// Renders the right-side quest detail view using Dear ImGui.
/// Shows header, prerequisites, objectives, required items, rewards, chain links, and flag warnings.
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
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Warning);
            ImGui.TextWrapped("Quest not found in guide data.");
            ImGui.PopStyleColor();
            return;
        }

        ImGui.BeginChild("##DetailScroll", Vector2.Zero, false, ImGuiWindowFlags.None);

        DrawHeader(quest);
        DrawPrerequisites(quest);
        DrawObjectives(quest);
        DrawRequiredItems(quest);
        DrawRewards(quest);
        DrawChain(quest);
        DrawFlags(quest);

        ImGui.Spacing();
        ImGui.Separator();
        ImGui.Spacing();
        DrawActionButtons(quest);

        ImGui.EndChild();
    }

    private void DrawHeader(QuestEntry quest)
    {
        // Quest name in header color, scaled up via a font size push if available.
        // ImGui.NET doesn't have per-call font size; use color to distinguish.
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.Header);
        ImGui.TextWrapped(quest.DisplayName);
        ImGui.PopStyleColor();

        // Quest giver and zone
        var giver = quest.Acquisition?.Find(a => a.Method == "dialog");
        if (giver?.SourceName != null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text($"Given by: {giver.SourceName}");
            ImGui.PopStyleColor();
        }

        if (quest.ZoneContext != null)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
            ImGui.Text($"Zone: {quest.ZoneContext}");
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

    private void DrawPrerequisites(QuestEntry quest)
    {
        if (quest.Prerequisites == null || quest.Prerequisites.Count == 0)
            return;

        // Collapsed by default (no DefaultOpen flag)
        if (!ImGui.CollapsingHeader("Prerequisites", ImGuiTreeNodeFlags.None))
            return;

        ImGui.Indent(Theme.IndentWidth);
        foreach (var prereqName in quest.Prerequisites)
        {
            // Try to find this prerequisite in data to check completion.
            // Prerequisites are stored as display names, so we search all entries.
            bool completed = IsPrerequisiteCompleted(prereqName);
            var color = completed ? Theme.QuestCompleted : Theme.TextPrimary;
            var prefix = completed ? "\u2713 " : "\u25cb "; // ✓ or ○

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            ImGui.Text($"{prefix}{prereqName}");
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private bool IsPrerequisiteCompleted(string prereqName)
    {
        // Prerequisites are display names. Walk data to find a matching DBName.
        foreach (var entry in _data.All)
        {
            if (string.Equals(entry.DisplayName, prereqName, StringComparison.OrdinalIgnoreCase))
                return _state.IsCompleted(entry.DBName);
        }
        return false;
    }

    private void DrawObjectives(QuestEntry quest)
    {
        if (quest.Steps == null || quest.Steps.Count == 0)
            return;

        // Expanded by default
        if (!ImGui.CollapsingHeader("Objectives", ImGuiTreeNodeFlags.DefaultOpen))
            return;

        int currentStepIndex = DetermineCurrentStep(quest);

        ImGui.Indent(Theme.IndentWidth);
        for (int i = 0; i < quest.Steps.Count; i++)
        {
            var step = quest.Steps[i];

            if (i < currentStepIndex)
                DrawCompletedStep(step);
            else if (i == currentStepIndex)
                DrawCurrentStep(step);
            else
                DrawFutureStep(step);
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private void DrawCompletedStep(QuestStep step)
    {
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestCompleted);
        ImGui.Text($"\u2713 {step.Order}. {step.Description}");
        ImGui.PopStyleColor();
    }

    private void DrawCurrentStep(QuestStep step)
    {
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.QuestActive);
        string text = $">> {step.Order}. {step.Description}";

        // Collect steps: show have/need count
        if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
        {
            int have = _state.CountItemInInventory(step.TargetName);
            text += $" ({have}/{step.Quantity})";
        }

        ImGui.Text(text);
        ImGui.PopStyleColor();

        DrawStepExtras(step);
    }

    private void DrawFutureStep(QuestStep step)
    {
        ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
        string text = $"\u25cb {step.Order}. {step.Description}";

        // Collect steps: show have/need count
        if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
        {
            int have = _state.CountItemInInventory(step.TargetName);
            text += $" ({have}/{step.Quantity})";
        }

        ImGui.Text(text);
        ImGui.PopStyleColor();

        DrawStepExtras(step);
    }

    /// <summary>
    /// Renders drop sources and tips indented below a step.
    /// </summary>
    private void DrawStepExtras(QuestStep step)
    {
        ImGui.Indent(Theme.IndentWidth);

        // Show drop sources for collect steps by finding matching required items
        if (step.Action == "collect" && step.TargetName != null)
        {
            DrawDropSourcesForItem(step.TargetName);
        }

        // Tips (collapsed by default)
        if (step.Tips != null && step.Tips.Count > 0)
        {
            if (ImGui.TreeNode($"Tips##{step.Order}"))
            {
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                foreach (var tip in step.Tips)
                    ImGui.TextWrapped(tip);
                ImGui.PopStyleColor();
                ImGui.TreePop();
            }
        }

        ImGui.Unindent(Theme.IndentWidth);
    }

    /// <summary>
    /// Find drop sources for an item by searching the quest's required items list.
    /// We search the currently displayed quest rather than taking it as a parameter
    /// to avoid threading the quest reference through every step helper.
    /// </summary>
    private void DrawDropSourcesForItem(string itemName)
    {
        var quest = _data.GetByDBName(_state.SelectedQuestDBName!);
        if (quest?.RequiredItems == null) return;

        foreach (var item in quest.RequiredItems)
        {
            if (!string.Equals(item.ItemName, itemName, StringComparison.OrdinalIgnoreCase))
                continue;

            if (item.DropSources != null)
            {
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                foreach (var ds in item.DropSources)
                {
                    var zone = ds.ZoneName != null ? $" ({ds.ZoneName})" : "";
                    ImGui.Text($"Drops from: {ds.CharacterName}{zone}");
                }
                ImGui.PopStyleColor();
            }
            break;
        }
    }

    /// <summary>
    /// Walk steps to find the first incomplete one. Mirrors GuideWindow.DetermineCurrentStep.
    /// </summary>
    private int DetermineCurrentStep(QuestEntry quest)
    {
        if (_state.IsCompleted(quest.DBName))
            return quest.Steps!.Count; // all done

        if (!_state.IsActive(quest.DBName))
            return 0; // not started

        for (int i = 0; i < quest.Steps!.Count; i++)
        {
            var step = quest.Steps[i];
            if (step.Action == "collect" && step.TargetName != null && step.Quantity.HasValue)
            {
                int have = _state.CountItemInInventory(step.TargetName);
                if (have < step.Quantity.Value)
                    return i;
            }
            else if (step.Action == "travel" && step.ZoneName != null)
            {
                // Can't match scene name to zone display name without a lookup.
                // Fall through — treated as complete so next step becomes current.
            }
            // talk, kill, shout, turn_in — can't detect completion, assume done
        }

        // All detectable steps done — point to last step
        return quest.Steps.Count - 1;
    }

    private void DrawRequiredItems(QuestEntry quest)
    {
        if (quest.RequiredItems == null || quest.RequiredItems.Count == 0)
            return;

        if (!ImGui.CollapsingHeader("Required Items", ImGuiTreeNodeFlags.None))
            return;

        ImGui.Indent(Theme.IndentWidth);
        foreach (var item in quest.RequiredItems)
        {
            int have = _state.CountItemInInventory(item.ItemName);
            var color = have >= item.Quantity ? Theme.QuestCompleted : Theme.TextPrimary;

            ImGui.PushStyleColor(ImGuiCol.Text, color);
            ImGui.Text($"{item.ItemName} ({have}/{item.Quantity})");
            ImGui.PopStyleColor();

            // Drop sources
            if (item.DropSources != null)
            {
                ImGui.Indent(Theme.IndentWidth);
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                foreach (var ds in item.DropSources)
                {
                    var zone = ds.ZoneName != null ? $" ({ds.ZoneName})" : "";
                    ImGui.Text($"Drops from: {ds.CharacterName}{zone}");
                }
                ImGui.PopStyleColor();
                ImGui.Unindent(Theme.IndentWidth);
            }

            // Vendor sources
            if (item.VendorSources != null)
            {
                ImGui.Indent(Theme.IndentWidth);
                ImGui.PushStyleColor(ImGuiCol.Text, Theme.TextSecondary);
                foreach (var vs in item.VendorSources)
                {
                    var zone = vs.ZoneName != null ? $" ({vs.ZoneName})" : "";
                    ImGui.Text($"Sold by: {vs.CharacterName}{zone}");
                }
                ImGui.PopStyleColor();
                ImGui.Unindent(Theme.IndentWidth);
            }
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private void DrawRewards(QuestEntry quest)
    {
        var r = quest.Rewards;
        if (r == null) return;
        if (r.XP == 0 && r.Gold == 0 && r.ItemName == null && r.FactionEffects == null)
            return;

        if (!ImGui.CollapsingHeader("Rewards", ImGuiTreeNodeFlags.None))
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

        ImGui.Unindent(Theme.IndentWidth);
    }

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
            // Selectable acts as clickable text — navigates to the linked quest
            if (ImGui.Selectable($"{arrow}{link.QuestName}##{link.QuestStableKey}"))
            {
                if (linkedQuest != null)
                    _state.SelectedQuestDBName = linkedQuest.DBName;
            }
            ImGui.PopStyleColor();
        }
        ImGui.Unindent(Theme.IndentWidth);
    }

    private void DrawFlags(QuestEntry quest)
    {
        var f = quest.Flags;
        if (f == null) return;

        bool hasWarnings = f.KillTurnInHolder || f.DestroyTurnInHolder || f.OncePerSpawnInstance;
        if (!hasWarnings) return;

        ImGui.Spacing();

        if (f.KillTurnInHolder)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Warning);
            ImGui.TextWrapped("\u26a0 Warning: Turning in this quest kills the NPC!");
            ImGui.PopStyleColor();
        }

        if (f.DestroyTurnInHolder)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Warning);
            ImGui.TextWrapped("\u26a0 Warning: Turning in this quest destroys the NPC!");
            ImGui.PopStyleColor();
        }

        if (f.OncePerSpawnInstance)
        {
            ImGui.PushStyleColor(ImGuiCol.Text, Theme.Warning);
            ImGui.TextWrapped("\u26a0 Note: Can only be turned in once per NPC spawn cycle.");
            ImGui.PopStyleColor();
        }
    }

    private static void DrawActionButtons(QuestEntry quest)
    {
        // Placeholder buttons — navigation system comes in Phase 4
        if (ImGui.Button("Track"))
        {
            BepInEx.Logging.Logger.CreateLogSource("AdventureGuide")
                .LogInfo($"[Track] {quest.DisplayName} ({quest.DBName})");
        }

        ImGui.SameLine();

        if (ImGui.Button("Navigate"))
        {
            BepInEx.Logging.Logger.CreateLogSource("AdventureGuide")
                .LogInfo($"[Navigate] {quest.DisplayName} ({quest.DBName})");
        }
    }
}
