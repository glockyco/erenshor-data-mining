using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TrackerFocusRankingTests
{
    [Fact]
    public void GetTrackerSceneRank_CurrentZoneLineRanksBelowCurrentZoneObjective()
    {
        var graph = new TestGraphBuilder()
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "A→B", scene: "ZoneA",
                destinationZoneKey: "zone:b", x: 10, y: 0, z: 0)
            .AddCharacter("character:guard", "Guard", scene: "ZoneA")
            .Build();

        var harness = SnapshotHarness.FromSnapshot(
            graph,
            new StateSnapshot { CurrentZone = "ZoneA" });

        var zoneLineNode = graph.GetNode("zl:ab")!;
        var guardNode = graph.GetNode("character:guard")!;
        var zoneLineTarget = MakeTarget(zoneLineNode, scene: "ZoneA", x: 10f);
        var guardTarget = MakeTarget(guardNode, scene: "ZoneA", x: 20f);

        int zoneLineRank = QuestResolutionService.GetTrackerSceneRank(
            zoneLineTarget, "ZoneA", harness.Router);
        int guardRank = QuestResolutionService.GetTrackerSceneRank(
            guardTarget, "ZoneA", harness.Router);

        Assert.Equal(1, zoneLineRank);
        Assert.Equal(0, guardRank);
        Assert.True(guardRank < zoneLineRank);
    }

    private static ResolvedQuestTarget MakeTarget(Node node, string scene, float x)
    {
        var ctx = new ResolvedNodeContext(node.Key, node);
        var semantic = new ResolvedActionSemantic(
            NavigationGoalKind.StartQuest,
            NavigationTargetKind.Character,
            ResolvedActionKind.Talk,
            null, null,
            keywordText: null,
            payloadText: null,
            targetIdentityText: node.DisplayName,
            contextText: null,
            rationaleText: null,
            zoneText: null,
            availabilityText: null,
            MarkerType.Objective,
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
            isActionable: true);
    }
}
