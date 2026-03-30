using AdventureGuide.Navigation;
using AdventureGuide.Views;

namespace AdventureGuide.Resolution;

/// <summary>
/// Canonical resolved answer for one quest in the current runtime state.
/// Every surface renders a projection of this model instead of rebuilding its
/// own frontier, targets, or summaries.
/// </summary>
public sealed class QuestResolution
{
    public string QuestKey { get; }
    public ViewNode? ViewRoot { get; }
    public IReadOnlyList<EntityViewNode> Frontier { get; }
    public IReadOnlyList<ResolvedQuestTarget> Targets { get; }
    public TrackerSummary TrackerSummary { get; }

    public QuestResolution(
        string questKey,
        ViewNode? viewRoot,
        IReadOnlyList<EntityViewNode> frontier,
        IReadOnlyList<ResolvedQuestTarget> targets,
        TrackerSummary trackerSummary)
    {
        QuestKey = questKey;
        ViewRoot = viewRoot;
        Frontier = frontier;
        Targets = targets;
        TrackerSummary = trackerSummary;
    }
}
