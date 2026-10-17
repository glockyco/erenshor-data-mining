using AdventureGuide.Data;

namespace AdventureGuide.Navigation;

/// <summary>Keeps a player's source choice while its prerequisites are followed.</summary>
internal sealed class SourceNavigationSelection
{
    private string? _questKey;
    private int _stepOrder;
    private SourceChoice? _choice;
    internal bool IsActive => _choice != null;
    internal SourceChoice? Choice => _choice;

    internal bool Select(SourceChoice choice, QuestStep step, QuestEntry quest)
    {
        if (!IsCurrent(ItemSourcePolicy.SourcesFor(quest, step), choice))
            return false;
        _questKey = quest.RuntimeKey;
        _stepOrder = step.Order;
        _choice = choice;
        return true;
    }

    internal void Clear()
    {
        _questKey = null;
        _choice = null;
    }

    internal bool IsFor(QuestEntry quest, QuestStep step) =>
        _choice != null && _questKey == quest.RuntimeKey && _stepOrder == step.Order;

    internal RequirementResolution Resolve(
        RequirementResolver resolver,
        QuestEntry quest,
        QuestStep step,
        string scene,
        ZoneLineEntry? pinnedLine = null
    ) => resolver.Resolve(quest, step, scene, pinnedLine, IsFor(quest, step) ? _choice : null);

    internal static bool IsCurrent(List<ItemSource>? sources, SourceChoice? choice) =>
        choice != null
        && ReferenceEquals(SourceChoice.FindContaining(sources, choice.Primary), choice);

    internal static bool ContainsMember(List<ItemSource>? sources, SourceChoice choice)
    {
        if (sources == null)
            return false;
        foreach (var source in sources)
            if (choice.Contains(source) || ContainsMember(source.Children, choice))
                return true;
        return false;
    }
}
