using AdventureGuide.Graph;
using AdventureGuide.Markers;
using AdventureGuide.Navigation;
using AdventureGuide.Resolution;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class CharacterMarkerPolicyTests
{
    [Fact]
    public void KillTarget_WithRelevantCorpse_KeepsActiveMarker()
    {
        var target = MakeTarget(ResolvedActionKind.Kill, isActionable: true);

        Assert.True(CharacterMarkerPolicy.ShouldEmitActiveMarker(target));
        Assert.True(CharacterMarkerPolicy.ShouldKeepQuestMarkerOnCorpse(target));
    }

    [Fact]
    public void KillTarget_WithoutRelevantCorpse_UsesRespawnMarkerOnly()
    {
        var target = MakeTarget(ResolvedActionKind.Kill, isActionable: false);

        Assert.False(CharacterMarkerPolicy.ShouldEmitActiveMarker(target));
        Assert.False(CharacterMarkerPolicy.ShouldKeepQuestMarkerOnCorpse(target));
    }

    [Fact]
    public void NonKillCharacterTarget_StillEmitsActiveMarkerWhenNonActionable()
    {
        var target = MakeTarget(ResolvedActionKind.Talk, isActionable: false);

        Assert.True(CharacterMarkerPolicy.ShouldEmitActiveMarker(target));
        Assert.False(CharacterMarkerPolicy.ShouldKeepQuestMarkerOnCorpse(target));
    }

    private static ResolvedQuestTarget MakeTarget(
        ResolvedActionKind actionKind,
        bool isActionable)
    {
        var node = new Node
        {
            Key = "character:test",
            Type = NodeType.Character,
            DisplayName = "Test NPC",
        };
        var ctx = new ResolvedNodeContext(node.Key, node);
        var semantic = new ResolvedActionSemantic(
            NavigationGoalKind.StartQuest,
            NavigationTargetKind.Character,
            actionKind,
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
            targetNodeKey: node.Key,
            scene: "ZoneA",
            sourceKey: "spawn:zonea:1:2:3",
            goalNode: ctx,
            targetNode: ctx,
            semantic: semantic,
            explanation: explanation,
            x: 1f,
            y: 2f,
            z: 3f,
            isActionable: isActionable);
    }
}
