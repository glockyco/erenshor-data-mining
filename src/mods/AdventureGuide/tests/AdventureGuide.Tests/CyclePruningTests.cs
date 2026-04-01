using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class CyclePruningTests
{
    // ── Zone access cycles ──────────────────────────────────────────────

    [Fact]
    public void ZoneAccessCycle_MarksCharacterAsPrunedCycle()
    {
        // Quest X has a step: talk to Character A who lives in Zone B.
        // Zone B is only accessible via a zone line that Quest X itself
        // unlocks — a circular dependency. Character A should be pruned.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:x", "Quest X", dbName: "QuestX")
            .AddCharacter("character:a", "Char A", scene: "ZoneB")
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 1, y: 0, z: 1)
            .AddEdge("quest:x", "character:a", EdgeType.StepTalk)
            .AddEdge("quest:x", "zl:ab", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestX"],
            CurrentZone = "ZoneA",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var plan = harness.BuildPlan("quest:x");

        var charA = plan.EntityNodesByKey["character:a"];
        Assert.Equal(PlanStatus.PrunedCycle, charA.Status);
        Assert.Null(charA.UnlockRequirementId);
    }

    [Fact]
    public void ZoneAccessCycle_ResolvesSceneFromSpawnPoints()
    {
        // Gherist pattern: Character has no scene on the node itself, but
        // a spawn point in a locked zone. The plan builder must resolve the
        // spawn point scene to detect the zone access cycle.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:x", "Quest X", dbName: "QuestX")
            .AddItem("item:note", "Note")
            .AddCharacter("character:gherist", "Gherist") // no scene!
            .AddSpawnPoint("spawn:gherist", "Gherist Spawn", scene: "Locked")
            .AddZone("zone:start", "Start", scene: "Start")
            .AddZone("zone:locked", "Locked", scene: "Locked")
            .AddZoneLine("zl:start:locked", "ZL", scene: "Start",
                destinationZoneKey: "zone:locked", x: 1, y: 0, z: 1)
            .AddEdge("quest:x", "item:note", EdgeType.StepRead)
            .AddEdge("character:gherist", "item:note", EdgeType.DropsItem)
            .AddEdge("character:gherist", "spawn:gherist", EdgeType.HasSpawn)
            .AddEdge("quest:x", "zl:start:locked", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestX"],
            CurrentZone = "Start",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var plan = harness.BuildPlan("quest:x");

        // Gherist should be PrunedCycle because his spawn zone is locked
        // behind quest:x itself.
        var gherist = plan.EntityNodesByKey["character:gherist"];
        Assert.Equal(PlanStatus.PrunedCycle, gherist.Status);
    }

    [Fact]
    public void ZoneAccessCycle_PreservesNonCyclicBlockingSource()
    {
        // Zone B is locked behind two quests: quest:x (the root, cyclic) and
        // quest:gate (not cyclic). Only quest:x should be dropped; quest:gate
        // should remain as the unlock requirement.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:x", "Quest X", dbName: "QuestX")
            .AddQuest("quest:gate", "Gate Quest", dbName: "GateQuest")
            .AddCharacter("character:a", "Char A", scene: "ZoneB")
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 1, y: 0, z: 1)
            .AddEdge("quest:x", "character:a", EdgeType.StepTalk)
            .AddEdge("quest:x", "zl:ab", EdgeType.UnlocksZoneLine)
            .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestX"],
            CurrentZone = "ZoneA",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var plan = harness.BuildPlan("quest:x");

        // Character A should NOT be PrunedCycle — it has a real unlock path.
        var charA = plan.EntityNodesByKey["character:a"];
        Assert.NotEqual(PlanStatus.PrunedCycle, charA.Status);
        Assert.NotNull(charA.UnlockRequirementId);
        var group = Assert.IsType<PlanGroupNode>(plan.GetNode(charA.UnlockRequirementId!.Value));
        Assert.Contains(group.Outgoing, l => l.ToId == (PlanNodeId)"quest:gate");
    }

    // ── Direct quest prerequisite cycles ────────────────────────────────

    [Fact]
    public void QuestPrereqCycle_CreatesCycleStub()
    {
        // Quest A requires Quest B, Quest B requires Quest A.
        // When building Quest A, B is encountered as a prerequisite.
        // B's prerequisite on A should become a cycle stub.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA")
            .AddQuest("quest:b", "Quest B", dbName: "QuestB")
            .AddEdge("quest:a", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:a", EdgeType.RequiresQuest)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:a");

        // Quest B's prerequisite group should contain a cycle stub (not the
        // real quest:a entity).
        var questB = plan.EntityNodesByKey["quest:b"];
        var prereqGroup = (PlanGroupNode)plan.GetNode("quest:b:prerequisites:allof")!;
        Assert.Single(prereqGroup.Outgoing);

        var stubLink = prereqGroup.Outgoing[0];
        var stubNode = plan.GetNode(stubLink.ToId);
        Assert.NotNull(stubNode);
        Assert.Equal(PlanStatus.PrunedCycle, stubNode!.Status);
        Assert.StartsWith("cycle:quest:a:", stubNode.Id.Value);
    }

    [Fact]
    public void QuestPrereqCycle_PropagatesToPrunedInfeasible()
    {
        // Quest A → Quest B → Quest A (cycle).
        // B has no other path, so B becomes PrunedInfeasible.
        // A has only B as a prereq, so A also becomes PrunedInfeasible.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA")
            .AddQuest("quest:b", "Quest B", dbName: "QuestB")
            .AddEdge("quest:a", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:a", EdgeType.RequiresQuest)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:a");

        var questB = plan.EntityNodesByKey["quest:b"];
        Assert.Equal(PlanStatus.PrunedInfeasible, questB.Status);

        var questA = plan.EntityNodesByKey["quest:a"];
        Assert.Equal(PlanStatus.PrunedInfeasible, questA.Status);
    }

    // ── AnyOf survival: one cyclic branch, one valid ────────────────────

    [Fact]
    public void AnyOfSurvival_CyclicBranchPruned_ValidBranchSurvives()
    {
        // Quest A has two item sources for item:x — Character C (drops item)
        // in a zone locked by Quest A (cycle) and Character D (drops item)
        // in a reachable zone.
        //
        // Structure:
        //   quest:a → item:x (step)
        //   item:x sources (AnyOf): character:c, character:d
        //   character:c is in ZoneB (locked by quest:a → cycle)
        //   character:d is in ZoneA (reachable)
        //
        // character:c should be PrunedCycle, item:x should remain Available.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA")
            .AddItem("item:x", "Item X")
            .AddCharacter("character:c", "Char C", scene: "ZoneB")
            .AddCharacter("character:d", "Char D", scene: "ZoneA")
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:b", "Zone B", scene: "ZoneB")
            .AddZoneLine("zl:ab", "ZL A→B", scene: "ZoneA", destinationZoneKey: "zone:b",
                x: 1, y: 0, z: 1)
            .AddEdge("quest:a", "item:x", EdgeType.StepRead)
            .AddEdge("character:c", "item:x", EdgeType.DropsItem)
            .AddEdge("character:d", "item:x", EdgeType.DropsItem)
            .AddEdge("quest:a", "zl:ab", EdgeType.UnlocksZoneLine)
            .Build();

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestA"],
            CurrentZone = "ZoneA",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var plan = harness.BuildPlan("quest:a");

        var charC = plan.EntityNodesByKey["character:c"];
        Assert.Equal(PlanStatus.PrunedCycle, charC.Status);

        var charD = plan.EntityNodesByKey["character:d"];
        Assert.NotEqual(PlanStatus.PrunedCycle, charD.Status);
        Assert.NotEqual(PlanStatus.PrunedInfeasible, charD.Status);

        // The item sources group (AnyOf) should still be feasible because
        // character:d provides a valid path.
        var itemX = plan.EntityNodesByKey["item:x"];
        Assert.NotEqual(PlanStatus.PrunedInfeasible, itemX.Status);

        // Quest A itself should remain available.
        var questA = plan.EntityNodesByKey["quest:a"];
        Assert.NotEqual(PlanStatus.PrunedInfeasible, questA.Status);
    }

    // ── AllOf propagation ───────────────────────────────────────────────

    [Fact]
    public void AllOfPropagation_CyclicChildMakesGroupInfeasible()
    {
        // Quest A requires prereq Quest B. Quest B requires prereq Quest A.
        // The prerequisites group is AllOf. Since B's only prereq is cyclic,
        // B becomes PrunedInfeasible, making A's prereqs infeasible too.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA")
            .AddQuest("quest:b", "Quest B", dbName: "QuestB")
            .AddEdge("quest:a", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:a", EdgeType.RequiresQuest)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:a");

        // B's prerequisite group should be PrunedInfeasible.
        var prereqGroupB = (PlanGroupNode)plan.GetNode("quest:b:prerequisites:allof")!;
        Assert.Equal(PlanStatus.PrunedInfeasible, prereqGroupB.Status);

        // A's prerequisite group should also be PrunedInfeasible (B is infeasible).
        var prereqGroupA = (PlanGroupNode)plan.GetNode("quest:a:prerequisites:allof")!;
        Assert.Equal(PlanStatus.PrunedInfeasible, prereqGroupA.Status);
    }

    // ── Deeper cycle: A → B → C → B ────────────────────────────────────

    [Fact]
    public void DeeperCycle_PrunesOnlyCyclicBranch()
    {
        // Quest A has step item:b.
        // Item B has two sources (AnyOf):
        //   - Character C (in Zone Z, locked by Quest B which requires Item B → cycle)
        //   - Character D (in reachable zone)
        //
        // The C path creates a cycle: item:b → character:c → (unlock) quest:b → item:b.
        // The D path is valid.
        // Item B should remain Available because of the AnyOf survival.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA")
            .AddQuest("quest:b", "Quest B", dbName: "QuestB")
            .AddItem("item:b", "Item B")
            .AddCharacter("character:c", "Char C", scene: "ZoneZ")
            .AddCharacter("character:d", "Char D", scene: "ZoneA")
            .AddZone("zone:a", "Zone A", scene: "ZoneA")
            .AddZone("zone:z", "Zone Z", scene: "ZoneZ")
            .AddZoneLine("zl:az", "ZL A→Z", scene: "ZoneA", destinationZoneKey: "zone:z",
                x: 1, y: 0, z: 1)
            .AddEdge("quest:a", "item:b", EdgeType.StepRead)
            .AddEdge("character:c", "item:b", EdgeType.DropsItem)
            .AddEdge("character:d", "item:b", EdgeType.DropsItem)
            .AddEdge("quest:b", "zl:az", EdgeType.UnlocksZoneLine)
            .AddEdge("quest:b", "item:b", EdgeType.RequiresItem)
            .Build();

        var snapshot = new StateSnapshot
        {
            ActiveQuests = ["QuestA"],
            CurrentZone = "ZoneA",
        };
        var harness = SnapshotHarness.FromSnapshot(graph, snapshot);
        var plan = harness.BuildPlan("quest:a");

        // Character C should be PrunedInfeasible: its unlock requirement
        // (quest:b) became PrunedInfeasible because quest:b's required item
        // (item:b) creates a cycle back to the item currently being built.
        var charC = plan.EntityNodesByKey["character:c"];
        Assert.Equal(PlanStatus.PrunedInfeasible, charC.Status);

        // Character D is valid.
        var charD = plan.EntityNodesByKey["character:d"];
        Assert.NotEqual(PlanStatus.PrunedCycle, charD.Status);
        Assert.NotEqual(PlanStatus.PrunedInfeasible, charD.Status);

        // Item B is still feasible via D.
        var itemB = plan.EntityNodesByKey["item:b"];
        Assert.NotEqual(PlanStatus.PrunedInfeasible, itemB.Status);

        // Quest A is still feasible.
        var questA = plan.EntityNodesByKey["quest:a"];
        Assert.NotEqual(PlanStatus.PrunedInfeasible, questA.Status);
    }

    // ── Memoization: subtree built once ─────────────────────────────────

    [Fact]
    public void MemoizedSubtree_ReusedAcrossReferences()
    {
        // Quest A and Quest X both require Quest B.
        // Quest B has a cycle through Quest C (B → C → B).
        // B should be built once, resolved, and reused when X references it.
        // Both A and X should see B in the same state.
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA")
            .AddQuest("quest:x", "Quest X", dbName: "QuestX")
            .AddQuest("quest:b", "Quest B", dbName: "QuestB")
            .AddQuest("quest:c", "Quest C", dbName: "QuestC")
            .AddCharacter("character:turn", "Turn-in")
            .AddEdge("quest:a", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:a", "quest:x", EdgeType.RequiresQuest)
            .AddEdge("quest:x", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:c", EdgeType.RequiresQuest)
            .AddEdge("quest:c", "quest:b", EdgeType.RequiresQuest)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:a");

        // B should be PrunedInfeasible (cycle through C, no alternative path).
        var questB = plan.EntityNodesByKey["quest:b"];
        Assert.Equal(PlanStatus.PrunedInfeasible, questB.Status);

        // There should be exactly one real entity for B (stubs are separate).
        Assert.True(plan.EntityNodesByKey.ContainsKey("quest:b"));

        // A's prerequisite group links to both B (infeasible) and X.
        // Since it's AllOf, A should also be infeasible.
        var questA = plan.EntityNodesByKey["quest:a"];
        Assert.Equal(PlanStatus.PrunedInfeasible, questA.Status);
    }

    // ── Pure graph-only build (no runtime state) ────────────────────────

    [Fact]
    public void PureGraphBuild_CycleStubsCreatedWithoutRuntimeState()
    {
        // Verify cycle detection works even without a GameState (the
        // single-arg QuestPlanBuilder constructor).
        var graph = new TestGraphBuilder()
            .AddQuest("quest:a", "Quest A", dbName: "QuestA")
            .AddQuest("quest:b", "Quest B", dbName: "QuestB")
            .AddEdge("quest:a", "quest:b", EdgeType.RequiresQuest)
            .AddEdge("quest:b", "quest:a", EdgeType.RequiresQuest)
            .Build();

        var plan = new QuestPlanBuilder(graph).Build("quest:a");

        // Should not throw, and cycle stubs should exist.
        var prereqGroupB = (PlanGroupNode)plan.GetNode("quest:b:prerequisites:allof")!;
        Assert.Single(prereqGroupB.Outgoing);
        var stubNode = plan.GetNode(prereqGroupB.Outgoing[0].ToId);
        Assert.NotNull(stubNode);
        Assert.Equal(PlanStatus.PrunedCycle, stubNode!.Status);
    }
}
