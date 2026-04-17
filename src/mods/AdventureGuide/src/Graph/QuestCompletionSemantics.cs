using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Graph;

internal static class QuestCompletionSemantics
{
    private const byte KeywordInteractionType = 1;

    public static bool HasTurnInPayload(CompiledGuideModel guide, Node questNode) =>
        questNode.Type == NodeType.Quest
        && (
            guide.OutEdges(questNode.Key, EdgeType.RequiresItem).Count > 0
            || guide.OutEdges(questNode.Key, EdgeType.RequiresMaterial).Count > 0
        );

    public static bool UsesKeywordInteraction(byte interactionType, string? keyword) =>
        interactionType == KeywordInteractionType && !string.IsNullOrEmpty(keyword);
}
