using AdventureGuide.Data;

namespace AdventureGuide.Navigation;

/// <summary>Formats the short labels shown beneath world markers.</summary>
public static class MarkerTextFormatter
{
    /// <summary>Format sub-text for turn-in markers: "Give {name}" or "Give {n} items".</summary>
    public static string FormatTurnInText(QuestEntry quest, CompletionSource comp)
    {
        if (quest.RequiredItems == null || quest.RequiredItems.Count == 0)
        {
            if (comp.Keyword != null)
                return $"Say '{comp.Keyword}'";
            return "Talk to";
        }

        // Filter out or_group alternatives — only count truly required items
        int count = 0;
        string? firstName = null;
        foreach (var ri in quest.RequiredItems)
        {
            if (ri.OrGroup != null)
                continue;
            count++;
            firstName ??= ri.ItemName;
        }

        if (count == 0)
        {
            if (comp.Keyword != null)
                return $"Say '{comp.Keyword}'";
            return "Talk to";
        }
        if (count == 1)
            return $"Give {firstName}";
        return $"Give {count} items";
    }

    /// <summary>Format sub-text for objective step markers based on step action.</summary>
    public static string FormatStepActionText(QuestStep step)
    {
        return step.Action switch
        {
            "talk" when step.Keyword != null => $"Say '{step.Keyword}'",
            "talk" => "Talk to",
            "turn_in" => "Turn in",
            "buy" => "Buy",
            "loot" => "Loot",
            "shout" when step.Keyword != null => $"Shout '{step.Keyword}'",
            "shout" => "Shout near",
            "kill" when step.Quantity > 1 => $"Kill ({step.Quantity})",
            "kill" => "Kill",
            _ => "Talk to",
        };
    }
}
