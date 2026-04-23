using AdventureGuide.Resolution;

namespace AdventureGuide.UI.Tree;

internal static class SpecTreeRecordState
{
    public static int? FindBlockingZoneLineNodeId(QuestResolutionRecord record, string? targetScene)
    {
        return record.TryGetBlockingZoneLineNodeId(targetScene, out int zoneLineNodeId)
            ? zoneLineNodeId
            : null;
    }
}
