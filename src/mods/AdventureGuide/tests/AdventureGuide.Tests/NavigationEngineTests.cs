using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class NavigationEngineTests
{
    [Fact]
    public void ComputeNavScore_IgnoresBlockedPathAcrossQuests()
    {
        var blockedSameZone = new SelectedNavTarget
        {
            Target = MakeTarget(scene: "ZoneA", x: 5f, isBlockedPath: true),
            IsSameZone = true,
            IsBlockedPath = true,
        };
        var directCrossZone = new SelectedNavTarget
        {
            Target = MakeTarget(scene: "ZoneB", x: 500f, isBlockedPath: false),
            IsSameZone = false,
            HopCount = 1,
            IsBlockedPath = false,
        };

        float blockedScore = NavigationScore.Compute(blockedSameZone, 0f, 0f, 0f);
        float directScore = NavigationScore.Compute(directCrossZone, 0f, 0f, 0f);

        Assert.True(blockedScore < directScore);
    }

    [Fact]
    public void ComputeNavScore_BlockedPathDoesNotAffectSameZoneDistanceOrdering()
    {
        var blockedNear = new SelectedNavTarget
        {
            Target = MakeTarget(scene: "ZoneA", x: 10f, isBlockedPath: true),
            IsSameZone = true,
            IsBlockedPath = true,
        };
        var directFar = new SelectedNavTarget
        {
            Target = MakeTarget(scene: "ZoneA", x: 100f, isBlockedPath: false),
            IsSameZone = true,
            IsBlockedPath = false,
        };

        float blockedScore = NavigationScore.Compute(blockedNear, 0f, 0f, 0f);
        float directScore = NavigationScore.Compute(directFar, 0f, 0f, 0f);

        Assert.True(blockedScore < directScore);
    }

    private static ResolvedQuestTarget MakeTarget(string scene, float x, bool isBlockedPath)
    {
        var node = new Node { Key = "node:" + x, Type = NodeType.Character, DisplayName = "Target" };
        var ctx = new ResolvedNodeContext(node.Key, node);
        var semantic = new ResolvedActionSemantic(
            NavigationGoalKind.StartQuest,
            NavigationTargetKind.Character,
            ResolvedActionKind.Talk,
            null,
            null,
            keywordText: null,
            payloadText: null,
            targetIdentityText: node.DisplayName,
            contextText: null,
            rationaleText: null,
            zoneText: null,
            availabilityText: null,
            QuestMarkerKind.Objective,
            markerPriority: 0);
        var explanation = new NavigationExplanation(
            NavigationGoalKind.StartQuest,
            NavigationTargetKind.Character,
            ctx,
            ctx,
            node.DisplayName,
            node.DisplayName,
            zoneText: null,
            secondaryText: null,
            tertiaryText: null);

        return new ResolvedQuestTarget(
            node.Key,
            scene,
            sourceKey: node.Key,
            ctx,
            ctx,
            semantic,
            explanation,
            x,
            y: 0f,
            z: 0f,
            isActionable: true,
            isBlockedPath: isBlockedPath);
    }
}
