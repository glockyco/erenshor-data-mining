using AdventureGuide.Data;

namespace AdventureGuide.Navigation;

/// <summary>Keeps a player's source choice while its prerequisites are followed.</summary>
internal sealed class SourceNavigationSelection
{
    private string? _questKey;
    private int _stepOrder;
    private ItemSource? _source;
    internal bool IsActive => _source != null;
    internal ItemSource? Source => _source;

    internal bool Select(ItemSource source, QuestStep step, QuestEntry quest)
    {
        if (!Contains(ItemSourcePolicy.SourcesFor(quest, step), source))
            return false;
        _questKey = quest.RuntimeKey;
        _stepOrder = step.Order;
        _source = source;
        return true;
    }

    internal void Clear()
    {
        _questKey = null;
        _source = null;
    }

    internal bool IsFor(QuestEntry quest, QuestStep step) =>
        _source != null && _questKey == quest.RuntimeKey && _stepOrder == step.Order;

    internal RequirementResolution Resolve(
        RequirementResolver resolver,
        QuestEntry quest,
        QuestStep step,
        string scene,
        ZoneLineEntry? pinnedLine = null
    ) => resolver.Resolve(quest, step, scene, pinnedLine, IsFor(quest, step) ? _source : null);

    internal static bool Contains(List<ItemSource>? sources, ItemSource? selected)
    {
        if (sources == null || selected == null)
            return false;
        foreach (var source in sources)
            if (ReferenceEquals(source, selected) || Contains(source.Children, selected))
                return true;
        return false;
    }
}
