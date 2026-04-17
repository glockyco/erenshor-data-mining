using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Verifies the post-refactor contract: implicit quests are separated from
/// actionable quests so that MarkerComputer routes them through
/// EmitImplicitCompletionMarkers rather than full plan resolution.
/// </summary>
public sealed class QuestStateTrackerImplicitTests
{
    [Fact]
    public void ImplicitQuest_InCompletionScene_IsImplicitlyAvailable_NotActionable()
    {
        // Arrange: implicit quest whose completion NPC lives in Stowaway.
        var builder = new CompiledGuideBuilder()
            .AddQuest("quest:q", dbName: "QuestQ", implicit_: true)
            .AddCharacter("character:npc", scene: "Stowaway")
            .AddEdge("quest:q", "character:npc", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot { CurrentZone = "Stowaway" };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);

        // Act
        bool implicitlyAvailable = harness.Tracker.IsImplicitlyAvailable("QuestQ");
        bool actionable = harness.Tracker.IsActionable("QuestQ");
        var actionableNames = harness.Tracker.GetActionableQuestDbNames().ToList();
        var implicitNames = harness.Tracker.GetImplicitlyAvailableQuestDbNames().ToList();

        // Assert: implicit quest is available but NOT in the actionable set.
        // This is the gate that routes it through EmitImplicitCompletionMarkers
        // instead of full plan resolution.
        Assert.True(
            implicitlyAvailable,
            "Quest should be implicitly available in its completion scene."
        );
        Assert.False(
            actionable,
            "IsActionable must not return true -- no plan resolution should run."
        );
        Assert.DoesNotContain("QuestQ", actionableNames);
        Assert.Contains("QuestQ", implicitNames);
    }

    [Fact]
    public void ImplicitQuest_NotInCompletionScene_NotImplicitlyAvailable()
    {
        var builder = new CompiledGuideBuilder()
            .AddQuest("quest:q", dbName: "QuestQ", implicit_: true)
            .AddCharacter("character:npc", scene: "Stowaway")
            .AddEdge("quest:q", "character:npc", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot { CurrentZone = "Brake" };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);

        Assert.False(harness.Tracker.IsImplicitlyAvailable("QuestQ"));
        Assert.DoesNotContain("QuestQ", harness.Tracker.GetImplicitlyAvailableQuestDbNames());
    }

    [Fact]
    public void ImplicitQuest_WhenActive_IsActive_NotImplicitlyAvailable()
    {
        // Once the player has accepted the quest explicitly, it transitions to active.
        // IsImplicitlyAvailable explicitly excludes active quests.
        var builder = new CompiledGuideBuilder()
            .AddQuest("quest:q", dbName: "QuestQ", implicit_: true)
            .AddCharacter("character:npc", scene: "Stowaway")
            .AddEdge("quest:q", "character:npc", EdgeType.CompletedBy);

        var snapshot = new StateSnapshot { CurrentZone = "Stowaway", ActiveQuests = ["QuestQ"] };
        var harness = SnapshotHarness.FromSnapshot(builder.Build(), snapshot);

        Assert.True(harness.Tracker.IsActive("QuestQ"));
        Assert.False(
            harness.Tracker.IsImplicitlyAvailable("QuestQ"),
            "Active quest must not be treated as implicitly available."
        );
        Assert.True(harness.Tracker.IsActionable("QuestQ"), "Active quest must remain actionable.");
    }
}
