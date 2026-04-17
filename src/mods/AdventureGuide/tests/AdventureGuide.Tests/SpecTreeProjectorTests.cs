using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Plan;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI.Tree;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class SpecTreeProjectorTests
{
    private static int FindQuestIndex(AdventureGuide.CompiledGuide.CompiledGuide guide, string key)
    {
        Assert.True(guide.TryGetNodeId(key, out int nodeId));
        for (int questIndex = 0; questIndex < guide.QuestCount; questIndex++)
        {
            if (guide.QuestNodeId(questIndex) == nodeId)
            {
                return questIndex;
            }
        }

        throw new InvalidOperationException($"Quest '{key}' not found in compiled guide.");
    }

    [Fact]
    public void Root_children_format_player_facing_labels()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:pre", dbName: "PRE")
            .AddItem("item:gem")
            .AddCharacter("char:giver")
            .AddCharacter("char:wolf")
            .AddCharacter("char:turnin")
            .AddQuest(
                "quest:root",
                dbName: "ROOT",
                prereqs: new[] { "quest:pre" },
                givers: new[] { "char:giver" },
                completers: new[] { "char:turnin" },
                requiredItems: new[] { ("item:gem", 2) })
            .AddStep("quest:root", stepType: 3, targetKey: "char:wolf")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(
            guide,
            tracker,
            new UnlockPredicateEvaluator(guide, tracker),
            null,
            () => string.Empty);

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootQuestIndex);

        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Prerequisite && r.Label == "Requires: quest:pre");
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Giver && r.Label == "Talk to char:giver");
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Item && r.Label == "Collect: item:gem (0/2)" && !r.IsCompleted);
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Step && r.Label == "Kill char:wolf");
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Completer && r.Label == "Turn in to char:turnin");
    }

    [Fact]
    public void Item_children_hide_friendly_drop_sources_when_hostile_drop_exists()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:pelt")
            .AddCharacter("char:wolf", isFriendly: false)
            .AddCharacter("char:ranger", isFriendly: true)
            .AddCharacter("char:vendor")
            .AddItemSource("item:pelt", "char:wolf", edgeType: (byte)EdgeType.DropsItem)
            .AddItemSource("item:pelt", "char:ranger", edgeType: (byte)EdgeType.DropsItem)
            .AddItemSource("item:pelt", "char:vendor", edgeType: (byte)EdgeType.SellsItem)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:pelt", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(
            guide,
            tracker,
            new UnlockPredicateEvaluator(guide, tracker),
            null,
            () => string.Empty);

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRoot = projector.GetRootChildren(rootQuestIndex).Single(r => r.Kind == SpecTreeKind.Item);
        var children = projector.GetChildren(itemRoot);

        Assert.Contains(children, child => child.Label == "Drops from: char:wolf");
        Assert.DoesNotContain(children, child => child.Label == "Drops from: char:ranger");
        Assert.Contains(children, child => child.Label == "Vendor: char:vendor");
    }

    [Fact]
    public void Blocked_nodes_expose_unlock_requirements()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:unlock", dbName: "UNLOCK")
            .AddItem("item:pelt")
            .AddCharacter("char:wolf")
            .AddItemSource("item:pelt", "char:wolf", edgeType: (byte)EdgeType.DropsItem)
            .AddUnlockPredicate("char:wolf", "quest:unlock")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:pelt", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(
            guide,
            tracker,
            new UnlockPredicateEvaluator(guide, tracker),
            null,
            () => string.Empty);

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRoot = projector.GetRootChildren(rootQuestIndex).Single(r => r.Kind == SpecTreeKind.Item);
        var source = projector.GetChildren(itemRoot).Single();

        Assert.True(source.IsBlocked);

        var unlocks = projector.GetUnlockChildren(source);

        Assert.Single(unlocks);
        Assert.Equal("Requires: quest:unlock", unlocks[0].Label);
        Assert.False(unlocks[0].IsCompleted);
    }

    [Fact]
    public void Item_unlock_condition_expands_to_item_sources()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:key")
            .AddCharacter("char:enemy", isFriendly: false)
            .AddCharacter("char:npc")
            .AddItemSource("item:key", "char:enemy", edgeType: (byte)EdgeType.DropsItem, sourceType: (byte)NodeType.Character)
            .AddUnlockPredicate("char:npc", "item:key", checkType: 1)
            .AddQuest("quest:a", dbName: "QUESTA", completers: new[] { "char:npc" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = new SpecTreeProjector(guide, tracker, evaluator, null, () => string.Empty);

        int questIndex = FindQuestIndex(guide, "quest:a");
        var roots = projector.GetRootChildren(questIndex);
        var completerRef = roots.Single(r => r.Kind == SpecTreeKind.Completer);
        var unlockRefs = projector.GetUnlockChildren(completerRef);

        Assert.Single(unlockRefs);
        Assert.Equal(SpecTreeKind.Item, unlockRefs[0].Kind);

        var itemSources = projector.GetChildren(unlockRefs[0]);
        Assert.NotEmpty(itemSources);
        Assert.Contains(itemSources, s => s.Label.Contains("char:enemy"));
    }

    [Fact]
    public void Quest_unlock_condition_shows_as_prerequisite_kind()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:gate", dbName: "GATE")
            .AddCharacter("char:npc")
            .AddUnlockPredicate("char:npc", "quest:gate", checkType: 0)
            .AddQuest("quest:a", dbName: "QUESTA", completers: new[] { "char:npc" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = new SpecTreeProjector(guide, tracker, evaluator, null, () => string.Empty);

        int questIndex = FindQuestIndex(guide, "quest:a");
        var roots = projector.GetRootChildren(questIndex);
        var completerRef = roots.Single(r => r.Kind == SpecTreeKind.Completer);
        var unlockRefs = projector.GetUnlockChildren(completerRef);

        Assert.Single(unlockRefs);
        Assert.Equal(SpecTreeKind.Prerequisite, unlockRefs[0].Kind);
    }

    [Fact]
    public void Unlock_any_of_conditions_are_grouped()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:unlock-a", dbName: "UNLOCKA")
            .AddItem("item:key")
            .AddCharacter("char:npc")
            .AddUnlockPredicate("char:npc", "quest:unlock-a", group: 1, checkType: 0)
            .AddUnlockPredicate("char:npc", "item:key", group: 2, checkType: 1)
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:npc" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "ROOT" }, new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = new SpecTreeProjector(guide, tracker, evaluator, null, () => string.Empty);

        int questIndex = FindQuestIndex(guide, "quest:root");
        var completerRef = projector.GetRootChildren(questIndex).Single(r => r.Kind == SpecTreeKind.Completer);
        var unlockRefs = projector.GetUnlockChildren(completerRef);

        var anyOf = Assert.Single(unlockRefs);
        Assert.Equal(SpecTreeKind.Group, anyOf.Kind);
        Assert.Equal("Any of:", anyOf.Label);
        var options = projector.GetChildren(anyOf);
        Assert.Equal(2, options.Count);
    }

    [Fact]
    public void Prerequisite_node_expands_to_prereq_quest_root_children()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:completer")
            .AddQuest("quest:pre", dbName: "QUESTPRE", completers: new[] { "char:completer" })
            .AddQuest("quest:root", dbName: "QUESTROOT", prereqs: new[] { "quest:pre" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = new SpecTreeProjector(guide, tracker, evaluator, null, () => string.Empty);

        int rootIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootIndex);
        var prereqRef = roots.Single(r => r.Kind == SpecTreeKind.Prerequisite);
        var prereqChildren = projector.GetChildren(prereqRef);

        Assert.Single(prereqChildren);
        Assert.Equal(SpecTreeKind.Completer, prereqChildren[0].Kind);
    }

    [Fact]
        public void Source_in_locked_zone_is_blocked_and_shows_zone_line_unlock_requirements()
        {
            var builder = new CompiledGuideBuilder()
                .AddZone("zone:a", scene: "ZoneA")
                .AddZone("zone:b", scene: "ZoneB")
                .AddZoneLine("zl:ab", scene: "ZoneA", destinationZoneKey: "zone:b", x: 10f, y: 0f, z: 5f)
                .AddQuest("quest:gate", dbName: "GATE")
                .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
                .AddUnlockPredicate("zl:ab", "quest:gate")
                .AddItem("item:fish")
                .AddWater("water:pond", scene: "ZoneB", x: 1f, y: 2f, z: 3f)
                .AddItemSource("item:fish", "water:pond", edgeType: (byte)EdgeType.YieldsItem, sourceType: (byte)NodeType.Water)
                .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:fish", 1) });
            var harness = SnapshotHarness.FromSnapshot(builder.Build(), new StateSnapshot { CurrentZone = "ZoneA" });

            var tracker = new QuestPhaseTracker(harness.Guide);
            tracker.Initialize(Array.Empty<string>(), new[] { "ROOT" }, new Dictionary<string, int>(), Array.Empty<string>());
            var evaluator = new UnlockPredicateEvaluator(harness.Guide, tracker);
            var projector = new SpecTreeProjector(
                harness.Guide,
                tracker,
                evaluator,
                harness.Router,
                () => harness.Tracker.CurrentZone);

            int rootQuestIndex = FindQuestIndex(harness.Guide, "quest:root");
            var itemRef = projector.GetRootChildren(rootQuestIndex).Single(r => r.Kind == SpecTreeKind.Item);
            var sourceRef = Assert.Single(projector.GetChildren(itemRef));
            Assert.True(sourceRef.IsBlocked);

            var unlockChildren = projector.GetUnlockChildren(sourceRef);
            Assert.Contains(unlockChildren, child => child.Label == "Requires: quest:gate");
        }

    [Fact]
    public void Recipe_source_expands_to_required_materials()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:ore")
            .AddCharacter("char:wolf", isFriendly: false)
            .AddItemSource("item:ore", "char:wolf", edgeType: (byte)EdgeType.DropsItem, sourceType: (byte)NodeType.Character)
            .AddItem("item:key")
            .AddRecipe("recipe:key")
            .AddItemSource("item:key", "recipe:key", edgeType: (byte)EdgeType.Produces, sourceType: (byte)NodeType.Recipe)
            .AddEdge("recipe:key", "item:ore", EdgeType.RequiresMaterial, quantity: 1)
            .AddEdge("recipe:key", "item:key", EdgeType.Produces)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:key", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker), null, () => string.Empty);

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRef = projector.GetRootChildren(rootQuestIndex).Single(r => r.Kind == SpecTreeKind.Item);
        var recipeSource = Assert.Single(projector.GetChildren(itemRef));
        var materials = projector.GetChildren(recipeSource);

        Assert.Contains(materials, child => child.Kind == SpecTreeKind.Item && child.Label == "Collect: item:ore");
    }

    [Fact]
    public void Reward_quest_source_expands_to_reward_quest_tree()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:note")
            .AddCharacter("char:percy")
            .AddQuest("quest:percy", dbName: "PERCY", givers: new[] { "char:percy" })
            .AddEdge("quest:percy", "item:note", EdgeType.RewardsItem)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:note", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker), null, () => string.Empty);

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRef = projector.GetRootChildren(rootQuestIndex).Single(r => r.Kind == SpecTreeKind.Item);
        var questSource = Assert.Single(projector.GetChildren(itemRef));
        var questChildren = projector.GetChildren(questSource);

        Assert.Contains(questChildren, child => child.Kind == SpecTreeKind.Giver && child.Label == "Talk to char:percy");
    }

    [Fact]
    public void Ready_item_giver_expands_to_item_source_tree()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:torn-note")
            .AddCharacter("char:ghost")
            .AddItemSource("item:torn-note", "char:ghost", edgeType: (byte)EdgeType.DropsItem, sourceType: (byte)NodeType.Character)
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "item:torn-note" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker), null, () => string.Empty);

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var giverRef = Assert.Single(projector.GetRootChildren(rootQuestIndex), r => r.Kind == SpecTreeKind.Giver);
        var children = projector.GetChildren(giverRef);

        Assert.Contains(children, child => child.Kind == SpecTreeKind.Source && child.Label == "Drops from: char:ghost");
    }

    [Fact]
    public void Recursive_unlock_cycle_with_direct_alternative_hides_impossible_branch()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:lucian-open")
            .AddCharacter("char:lucian-locked")
            .AddItem("item:ritual-token")
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:lucian-open", "char:lucian-locked" })
            .AddUnlockPredicate("char:lucian-locked", "item:ritual-token", checkType: 1)
            .AddEdge("quest:root", "item:ritual-token", EdgeType.RewardsItem)
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "ROOT" }, new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker), null, () => string.Empty);

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var completers = projector.GetRootChildren(rootQuestIndex).Where(child => child.Kind == SpecTreeKind.Completer).ToArray();

        Assert.Single(completers);
        Assert.Equal("Turn in to char:lucian-open", completers[0].Label);
    }

    [Fact]
    public void Self_cyclic_unlock_only_target_is_hidden()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:lucian")
            .AddUnlockPredicate("char:lucian", "quest:root")
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:lucian" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker), null, () => string.Empty);

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootQuestIndex);

        Assert.DoesNotContain(roots, child => child.Kind == SpecTreeKind.Completer && child.Label.Contains("char:lucian", StringComparison.Ordinal));
    }
}
