using AdventureGuide.Data;

namespace AdventureGuide.Navigation;

/// <summary>Keeps a player's source choice while its prerequisites are followed.</summary>
internal sealed class SourceNavigationSelection
{
    private string? _questKey;
    private int _stepOrder;
    private SourceChoice? _choice;
    private SourceChoice? _inputParent;
    private List<ItemSource>? _inputSiblings;
    internal bool IsActive => _choice != null;
    internal SourceChoice? Choice => _choice;

    internal bool Select(SourceChoice choice, QuestStep step, QuestEntry quest)
    {
        if (!IsCurrent(ItemSourcePolicy.SourcesFor(quest, step), choice))
            return false;
        _questKey = quest.DBName;
        _stepOrder = step.Order;
        _choice = choice;
        _inputParent = null;
        _inputSiblings = null;
        if (choice.Primary.Type == "ingredient")
            FindInputParent(
                ItemSourcePolicy.SourcesFor(quest, step),
                choice.Primary,
                out _inputParent,
                out _inputSiblings
            );
        return true;
    }

    internal void Clear()
    {
        _questKey = null;
        _choice = null;
        _inputParent = null;
        _inputSiblings = null;
    }

    internal bool IsFor(QuestEntry quest, QuestStep step) =>
        _choice != null && _questKey == quest.DBName && _stepOrder == step.Order;

    internal RequirementResolution Resolve(
        RequirementResolver resolver,
        QuestEntry quest,
        QuestStep step,
        string scene,
        ZoneLineEntry? pinnedLine = null
    )
    {
        if (
            IsFor(quest, step)
            && _inputParent != null
            && _inputSiblings != null
            && !resolver.NeedsInput(_choice!.Primary, _inputSiblings)
        )
        {
            _choice = _inputParent;
            _inputParent = null;
            _inputSiblings = null;
        }
        return resolver.Resolve(
            quest,
            step,
            scene,
            pinnedLine,
            IsFor(quest, step) ? _choice : null
        );
    }

    private static bool FindInputParent(
        List<ItemSource>? sources,
        ItemSource input,
        out SourceChoice? parent,
        out List<ItemSource>? siblings
    )
    {
        parent = null;
        siblings = null;
        if (sources == null)
            return false;
        foreach (var source in sources)
        {
            if (source.Children?.Contains(input) == true)
            {
                parent = SourceChoice.FindContaining(sources, source);
                siblings = source.Children;
                return true;
            }
            if (FindInputParent(source.Children, input, out parent, out siblings))
                return true;
        }
        return false;
    }

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
