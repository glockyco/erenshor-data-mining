using AdventureGuide.Navigation;
using AdventureGuide.Views;

namespace AdventureGuide.Resolution;

/// <summary>
/// Projects shared action semantics onto the world-marker surface.
/// Markers are local action affordances: one short action line plus the smallest
/// useful disambiguator or blocker text.
/// </summary>
internal static class MarkerTextBuilder
{
    public static MarkerInstruction BuildInstruction(
        ResolvedActionSemantic semantic,
        ViewNode? targetNode = null)
    {
        string primary = BuildPrimaryLine(semantic, targetNode);
        string? secondary = BuildSecondaryLine(semantic);
        string subText = string.IsNullOrEmpty(secondary) || primary == secondary
            ? primary
            : $"{primary}\n{secondary}";

        return new MarkerInstruction(
            semantic.PreferredMarkerType,
            subText,
            semantic.MarkerPriority);
    }

    private static string BuildPrimaryLine(ResolvedActionSemantic semantic, ViewNode? targetNode)
    {
        if (!string.IsNullOrEmpty(semantic.AvailabilityText))
            return semantic.AvailabilityText;

        return semantic.ActionKind switch
        {
            ResolvedActionKind.Talk => "Talk to",
            ResolvedActionKind.SayKeyword => $"Say '{semantic.KeywordText}'",
            ResolvedActionKind.ShoutKeyword => $"Shout '{semantic.KeywordText}'",
            ResolvedActionKind.Kill when targetNode?.Edge?.Quantity is int quantity && quantity > 1
                => $"Kill ({quantity})",
            ResolvedActionKind.Kill => "Kill",
            ResolvedActionKind.Read => "Read",
            ResolvedActionKind.Travel => "Travel to",
            ResolvedActionKind.Gather => "Gather",
            ResolvedActionKind.Buy => "Buy",
            ResolvedActionKind.Give => "Give",
            ResolvedActionKind.CompleteQuest => "Complete",
            _ => "Talk to",
        };
    }

    public static string BuildCorpseSubText(ResolvedActionSemantic semantic)
    {
        if (!string.IsNullOrEmpty(semantic.PayloadText))
            return $"Loot\n{semantic.PayloadText}";

        return "Loot";
    }

    private static string? BuildSecondaryLine(ResolvedActionSemantic semantic)
    {
        if (!string.IsNullOrEmpty(semantic.PayloadText))
            return semantic.PayloadText;

        if (semantic.PreferredMarkerType is MarkerType.QuestGiver or MarkerType.QuestGiverRepeat or MarkerType.QuestGiverBlocked)
            return semantic.ContextText;

        return semantic.RationaleText;
    }
}
