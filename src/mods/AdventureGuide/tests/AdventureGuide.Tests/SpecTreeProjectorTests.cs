using AdventureGuide.Diagnostics;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;
using AdventureGuide.State;
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
    public void GetRootChildren_MatchesResolutionRecordFrontierPhases()
    {
        var harness = SpecTreeProjectorHarness.Build();
        int questIndex = harness.QuestIndex("RootQuest");
        var record = harness.Reader.ReadQuestResolution("quest:root", "SceneA");

        var roots = harness.Projector.GetRootChildren(questIndex);

        Assert.Contains(
            roots,
            root =>
                root.Kind == SpecTreeKind.Prerequisite
                && root.StableId
                    == $"node:{harness.Guide.QuestNodeId(record.Frontier[0].QuestIndex)}"
        );
    }

    [Fact]
    public void GetRootChildren_UsesResolutionServiceBackedProjectorConstruction()
    {
        var harness = SpecTreeProjectorHarness.Build();

        var roots = harness.Projector.GetRootChildren(harness.QuestIndex("RootQuest"));

        Assert.NotEmpty(roots);
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
                requiredItems: new[] { ("item:gem", 2) }
            )
            .AddStep("quest:root", stepType: 3, targetKey: "char:wolf")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootQuestIndex);

        Assert.Contains(
            roots,
            r => r.Kind == SpecTreeKind.Prerequisite && r.Label == "Requires: quest:pre"
        );
        Assert.Contains(
            roots,
            r => r.Kind == SpecTreeKind.Giver && r.Label == "Talk to char:giver"
        );
        Assert.Contains(
            roots,
            r =>
                r.Kind == SpecTreeKind.Item
                && r.Label == "Collect: item:gem (0/2)"
                && !r.IsCompleted
        );
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Step && r.Label == "Kill char:wolf");
        Assert.Contains(
            roots,
            r => r.Kind == SpecTreeKind.Completer && r.Label == "Talk to char:turnin"
        );
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
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRoot = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
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
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRoot = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
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
            .AddItemSource(
                "item:key",
                "char:enemy",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:npc", "item:key", checkType: 2)
            .AddQuest("quest:a", dbName: "QUESTA", completers: new[] { "char:npc" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

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
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int questIndex = FindQuestIndex(guide, "quest:a");
        var roots = projector.GetRootChildren(questIndex);
        var completerRef = roots.Single(r => r.Kind == SpecTreeKind.Completer);
        var unlockRefs = projector.GetUnlockChildren(completerRef);

        Assert.Single(unlockRefs);
        Assert.Equal(SpecTreeKind.Prerequisite, unlockRefs[0].Kind);
    }

    [Fact]
    public void Non_item_inventory_key_does_not_satisfy_unlock_condition_in_detail_tree()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:token")
            .AddCharacter("char:npc")
            .AddUnlockPredicate("char:npc", "char:token", checkType: 1)
            .AddQuest("quest:a", dbName: "QUESTA", completers: new[] { "char:npc" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "QUESTA" },
            new Dictionary<string, int> { ["char:token"] = 1 },
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int questIndex = FindQuestIndex(guide, "quest:a");
        var completerRef = projector
            .GetRootChildren(questIndex)
            .Single(r => r.Kind == SpecTreeKind.Completer);

        Assert.True(completerRef.IsBlocked);
        var unlockRef = Assert.Single(projector.GetUnlockChildren(completerRef));
        Assert.Equal(SpecTreeKind.Source, unlockRef.Kind);
        Assert.False(unlockRef.IsCompleted);
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
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int questIndex = FindQuestIndex(guide, "quest:root");
        var completerRef = projector
            .GetRootChildren(questIndex)
            .Single(r => r.Kind == SpecTreeKind.Completer);
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
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

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
            .AddZoneLine(
                "zl:ab",
                scene: "ZoneA",
                destinationZoneKey: "zone:b",
                x: 10f,
                y: 0f,
                z: 5f
            )
            .AddQuest("quest:gate", dbName: "GATE")
            .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
            .AddUnlockPredicate("zl:ab", "quest:gate")
            .AddItem("item:fish")
            .AddWater("water:pond", scene: "ZoneB", x: 1f, y: 2f, z: 3f)
            .AddItemSource(
                "item:fish",
                "water:pond",
                edgeType: (byte)EdgeType.YieldsItem,
                sourceType: (byte)NodeType.Water
            )
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:fish", 1) });
        var harness = SnapshotHarness.FromSnapshot(
            builder.Build(),
            new StateSnapshot { CurrentZone = "ZoneA" }
        );

        var tracker = new QuestPhaseTracker(harness.Guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var evaluator = new UnlockPredicateEvaluator(harness.Guide, tracker);
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(
                harness.Guide,
                tracker,
                zoneRouter: harness.Router,
                currentSceneProvider: () => harness.Tracker.CurrentZone
            )
            .Projector;

        int rootQuestIndex = FindQuestIndex(harness.Guide, "quest:root");
        var itemRef = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
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
            .AddItemSource(
                "item:ore",
                "char:wolf",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddItem("item:key")
            .AddRecipe("recipe:key")
            .AddItemSource(
                "item:key",
                "recipe:key",
                edgeType: (byte)EdgeType.Produces,
                sourceType: (byte)NodeType.Recipe
            )
            .AddEdge("recipe:key", "item:ore", EdgeType.RequiresMaterial, quantity: 1)
            .AddEdge("recipe:key", "item:key", EdgeType.Produces)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:key", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRef = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
        var recipeSource = Assert.Single(projector.GetChildren(itemRef));
        var materials = projector.GetChildren(recipeSource);

        Assert.Contains(
            materials,
            child => child.Kind == SpecTreeKind.Item && child.Label == "Collect: item:ore"
        );
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
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRef = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
        var questSource = Assert.Single(projector.GetChildren(itemRef));
        var questChildren = projector.GetChildren(questSource);

        Assert.Contains(
            questChildren,
            child => child.Kind == SpecTreeKind.Giver && child.Label == "Talk to char:percy"
        );
    }

    [Fact]
    public void Completed_reward_quest_source_is_marked_completed()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:note")
            .AddCharacter("char:percy")
            .AddQuest("quest:percy", dbName: "PERCY", givers: new[] { "char:percy" })
            .AddEdge("quest:percy", "item:note", EdgeType.RewardsItem)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:note", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            new[] { "PERCY" },
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRef = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
        var questSource = Assert.Single(projector.GetChildren(itemRef));

        Assert.True(questSource.IsCompleted);
    }

    [Fact]
    public void Ready_item_giver_expands_to_item_source_tree()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:torn-note")
            .AddCharacter("char:ghost")
            .AddItemSource(
                "item:torn-note",
                "char:ghost",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "item:torn-note" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var giverRef = Assert.Single(
            projector.GetRootChildren(rootQuestIndex),
            r => r.Kind == SpecTreeKind.Giver
        );
        var children = projector.GetChildren(giverRef);

        Assert.Contains(
            children,
            child => child.Kind == SpecTreeKind.Source && child.Label == "Drops from: char:ghost"
        );
    }

    [Fact]
    public async Task Shared_reward_subtrees_project_without_timing_out()
    {
        const int depth = 14;
        var builder = new CompiledGuideBuilder()
            .AddCharacter("char:leaf", scene: "Town", x: 1f, y: 2f, z: 3f)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:0", 1) });

        for (int i = 0; i <= depth; i++)
            builder.AddItem($"item:{i}");

        for (int i = 0; i < depth; i++)
        {
            builder
                .AddQuest(
                    $"quest:{i}:a",
                    dbName: $"Q{i}A",
                    requiredItems: new[] { ($"item:{i + 1}", 1) }
                )
                .AddQuest(
                    $"quest:{i}:b",
                    dbName: $"Q{i}B",
                    requiredItems: new[] { ($"item:{i + 1}", 1) }
                )
                .AddEdge($"quest:{i}:a", $"item:{i}", EdgeType.RewardsItem)
                .AddEdge($"quest:{i}:b", $"item:{i}", EdgeType.RewardsItem);
        }

        builder.AddItemSource(
            $"item:{depth}",
            "char:leaf",
            edgeType: (byte)EdgeType.GivesItem,
            sourceType: (byte)NodeType.Character
        );

        var guide = builder.Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var projectionTask = Task.Run(() => projector.GetRootChildren(rootQuestIndex));
        var completed = await Task.WhenAny(
            projectionTask,
            Task.Delay(TimeSpan.FromMilliseconds(500))
        );

        Assert.Same(projectionTask, completed);
        var itemRoot = Assert.Single(
            await projectionTask,
            child => child.Kind == SpecTreeKind.Item
        );
        Assert.NotEmpty(projector.GetChildren(itemRoot));
    }

    [Fact]
    public void Recursive_unlock_cycle_with_direct_alternative_hides_impossible_branch()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:lucian-open")
            .AddCharacter("char:lucian-locked")
            .AddItem("item:ritual-token")
            .AddQuest(
                "quest:root",
                dbName: "ROOT",
                completers: new[] { "char:lucian-open", "char:lucian-locked" }
            )
            .AddUnlockPredicate("char:lucian-locked", "item:ritual-token", checkType: 1)
            .AddEdge("quest:root", "item:ritual-token", EdgeType.RewardsItem)
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var completers = projector
            .GetRootChildren(rootQuestIndex)
            .Where(child => child.Kind == SpecTreeKind.Completer)
            .ToArray();

        Assert.Single(completers);
        Assert.Equal("Talk to char:lucian-open", completers[0].Label);
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
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootQuestIndex);

        Assert.DoesNotContain(
            roots,
            child =>
                child.Kind == SpecTreeKind.Completer
                && child.Label.Contains("char:lucian", StringComparison.Ordinal)
        );
    }

    [Fact]
    public void Accepted_quest_marks_accept_roots_completed()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver")
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "char:giver" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var giverRef = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Giver);

        Assert.True(giverRef.IsCompleted);
    }

    [Fact]
    public void Completed_quest_marks_all_projected_nodes_completed()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:gem")
            .AddCharacter("char:giver")
            .AddCharacter("char:wolf", isFriendly: false)
            .AddCharacter("char:turnin")
            .AddItemSource("item:gem", "char:wolf", edgeType: (byte)EdgeType.DropsItem)
            .AddQuest(
                "quest:root",
                dbName: "ROOT",
                givers: new[] { "char:giver" },
                completers: new[] { "char:turnin" },
                requiredItems: new[] { ("item:gem", 1) }
            )
            .AddStep("quest:root", stepType: 3, targetKey: "char:wolf")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            new[] { "ROOT" },
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootQuestIndex);
        var itemRoot = roots.Single(r => r.Kind == SpecTreeKind.Item);

        Assert.All(roots, root => Assert.True(root.IsCompleted));
        Assert.All(projector.GetChildren(itemRoot), child => Assert.True(child.IsCompleted));
    }

    [Fact]
    public void Item_requirement_completion_reverts_when_inventory_is_lost()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:gem")
            .AddCharacter("char:wolf", isFriendly: false)
            .AddItemSource("item:gem", "char:wolf", edgeType: (byte)EdgeType.DropsItem)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:gem", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int> { ["item:gem"] = 1 },
            Array.Empty<string>()
        );
        var (reader, projector) = ResolutionTestFactory.BuildSpecTreeProjector(
            guide,
            tracker,
            currentSceneProvider: () => string.Empty
        );

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var completedItem = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
        Assert.True(completedItem.IsCompleted);

        Assert.True(guide.TryGetNodeId("item:gem", out int itemNodeId));
        tracker.OnInventoryChanged(guide.FindItemIndex(itemNodeId), 0);
        reader.Engine.InvalidateFacts(
            new[] { new FactKey(FactKind.InventoryItemCount, "item:gem") }
        );
        projector.ResetProjectionCaches();

        var incompleteItem = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
        Assert.False(incompleteItem.IsCompleted);
        Assert.Contains(
            projector.GetChildren(incompleteItem),
            child => child.Label == "Drops from: char:wolf"
        );
    }

    [Fact]
    public void Completed_item_root_skips_descendant_cycle_probe()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:loop")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:loop", 1) })
            .AddEdge("quest:root", "item:loop", EdgeType.RewardsItem)
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int> { ["item:loop"] = 1 },
            Array.Empty<string>()
        );
        var diagnostics = new DiagnosticsCore(
            eventCapacity: 8,
            spanCapacity: 8,
            incidentCapacity: 4,
            incidentThresholds: IncidentThresholds.Disabled
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(
                guide,
                tracker,
                currentSceneProvider: () => string.Empty,
                diagnostics: diagnostics
            )
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var itemRoot = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Item);
        var span = Assert.Single(diagnostics.GetRecentSpans());

        Assert.True(itemRoot.IsCompleted);
        Assert.Equal(DiagnosticSpanKind.SpecTreeProjectRoot, span.Kind);
        Assert.Equal(0, span.Value1);
    }

    [Fact]
    public void Duplicate_blocking_requirement_groups_are_collapsed()
    {
        var builder = new CompiledGuideBuilder()
            .AddZone("zone:a", scene: "ZoneA")
            .AddZone("zone:b", scene: "ZoneB")
            .AddZoneLine(
                "zl:ab",
                scene: "ZoneA",
                destinationZoneKey: "zone:b",
                x: 10f,
                y: 0f,
                z: 5f
            )
            .AddQuest("quest:gate", dbName: "GATE")
            .AddEdge("quest:gate", "zl:ab", EdgeType.UnlocksZoneLine)
            .AddUnlockPredicate("zl:ab", "quest:gate")
            .AddCharacter("char:npc", scene: "ZoneB")
            .AddUnlockPredicate("char:npc", "quest:gate")
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:npc" });
        var harness = SnapshotHarness.FromSnapshot(
            builder.Build(),
            new StateSnapshot { CurrentZone = "ZoneA" }
        );

        var tracker = new QuestPhaseTracker(harness.Guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var evaluator = new UnlockPredicateEvaluator(harness.Guide, tracker);
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(
                harness.Guide,
                tracker,
                zoneRouter: harness.Router,
                currentSceneProvider: () => harness.Tracker.CurrentZone
            )
            .Projector;

        int rootQuestIndex = FindQuestIndex(harness.Guide, "quest:root");
        var completerRef = projector
            .GetRootChildren(rootQuestIndex)
            .Single(r => r.Kind == SpecTreeKind.Completer);

        var unlockChildren = projector.GetUnlockChildren(completerRef);
        var unlockRef = Assert.Single(unlockChildren);
        Assert.Equal(SpecTreeKind.Prerequisite, unlockRef.Kind);
        Assert.Equal("Requires: quest:gate", unlockRef.Label);
    }

    [Fact]
    public void Nested_prerequisite_that_only_cycles_to_ancestor_item_is_pruned()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:torn-note")
            .AddItem("item:ghostly-key")
            .AddItem("item:aetheria")
            .AddRecipe("recipe:ghostly-key")
            .AddCharacter("char:ghost")
            .AddCharacter("char:sivakayan")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:torn-note", 1) })
            .AddQuest(
                "quest:note",
                dbName: "NOTE",
                givers: new[] { "item:torn-note" },
                requiredItems: new[] { ("item:torn-note", 1) }
            )
            .AddItemSource(
                "item:torn-note",
                "char:ghost",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:ghost", "item:ghostly-key", checkType: 1)
            .AddItemSource(
                "item:ghostly-key",
                "recipe:ghostly-key",
                edgeType: (byte)EdgeType.Produces,
                sourceType: (byte)NodeType.Recipe
            )
            .AddEdge("recipe:ghostly-key", "item:aetheria", EdgeType.RequiresMaterial, quantity: 1)
            .AddItemSource(
                "item:aetheria",
                "char:sivakayan",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:sivakayan", "quest:note")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var tornNote = projector
            .GetRootChildren(rootQuestIndex)
            .Single(child => child.Label == "Collect: item:torn-note");
        var ghost = projector
            .GetChildren(tornNote)
            .Single(child => child.Label == "Drops from: char:ghost");
        var ghostlyKey = projector
            .GetUnlockChildren(ghost)
            .Single(child => child.Label == "Requires: item:ghostly-key");
        var recipe = projector
            .GetChildren(ghostlyKey)
            .Single(child => child.Label == "Crafted via: recipe:ghostly-key");
        var aetheria = projector
            .GetChildren(recipe)
            .Single(child => child.Label == "Collect: item:aetheria");

        Assert.DoesNotContain(
            projector.GetChildren(aetheria),
            child => child.Label == "Drops from: char:sivakayan"
        );
    }

    [Fact]
    public void Item_giver_without_visible_acquisition_source_is_pruned()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:marching-orders")
            .AddCharacter("char:gherist")
            .AddQuest("quest:root", dbName: "ROOT", givers: new[] { "item:marching-orders" })
            .AddItemSource(
                "item:marching-orders",
                "char:gherist",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:gherist", "quest:root")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            Array.Empty<string>(),
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");

        Assert.DoesNotContain(
            projector.GetRootChildren(rootQuestIndex),
            child => child.Label == "Read item:marching-orders"
        );
    }

    [Fact]
    public void Prerequisite_quest_with_only_pruned_completion_paths_prunes_locked_source()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:torn-note")
            .AddItem("item:marching-orders")
            .AddItem("item:ghostly-key")
            .AddItem("item:aetheria")
            .AddRecipe("recipe:ghostly-key")
            .AddCharacter("char:ghost")
            .AddCharacter("char:sivakayan")
            .AddCharacter("char:gherist")
            .AddCharacter("char:lucian")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:torn-note", 1) })
            .AddQuest(
                "quest:note",
                dbName: "NOTE",
                givers: new[] { "item:marching-orders" },
                completers: new[] { "char:lucian" },
                requiredItems: new[] { ("item:torn-note", 1) }
            )
            .AddItemSource(
                "item:torn-note",
                "char:ghost",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:ghost", "item:ghostly-key", checkType: 1)
            .AddItemSource(
                "item:ghostly-key",
                "recipe:ghostly-key",
                edgeType: (byte)EdgeType.Produces,
                sourceType: (byte)NodeType.Recipe
            )
            .AddEdge("recipe:ghostly-key", "item:aetheria", EdgeType.RequiresMaterial, quantity: 1)
            .AddItemSource(
                "item:aetheria",
                "char:sivakayan",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:sivakayan", "quest:note")
            .AddItemSource(
                "item:marching-orders",
                "char:gherist",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:gherist", "quest:note")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var tornNote = projector
            .GetRootChildren(rootQuestIndex)
            .Single(child => child.Label == "Collect: item:torn-note");
        var ghost = projector
            .GetChildren(tornNote)
            .Single(child => child.Label == "Drops from: char:ghost");
        var ghostlyKey = projector
            .GetUnlockChildren(ghost)
            .Single(child => child.Label == "Requires: item:ghostly-key");
        var recipe = projector
            .GetChildren(ghostlyKey)
            .Single(child => child.Label == "Crafted via: recipe:ghostly-key");
        var aetheria = projector
            .GetChildren(recipe)
            .Single(child => child.Label == "Collect: item:aetheria");

        Assert.DoesNotContain(
            projector.GetChildren(aetheria),
            child => child.Label == "Drops from: char:sivakayan"
        );
    }

    [Fact]
    public void Any_of_unlock_prunes_cyclic_option_and_keeps_viable_alternative()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:root")
            .AddCharacter("char:locked")
            .AddQuest("quest:cyclic", dbName: "CYCLIC", requiredItems: new[] { ("item:root", 1) })
            .AddQuest("quest:viable", dbName: "VIABLE")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:root", 1) })
            .AddItemSource(
                "item:root",
                "char:locked",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:locked", "quest:cyclic", group: 1)
            .AddUnlockPredicate("char:locked", "quest:viable", group: 2)
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var rootItem = projector
            .GetRootChildren(rootQuestIndex)
            .Single(child => child.Label == "Collect: item:root");
        var source = projector
            .GetChildren(rootItem)
            .Single(child => child.Label == "Drops from: char:locked");
        var unlockChildren = projector.GetUnlockChildren(source);

        var option = Assert.Single(unlockChildren);
        Assert.Equal("Any of:", option.Label);
        var viable = Assert.Single(option.SyntheticChildren!);
        Assert.Equal("Requires: quest:viable", viable.Label);
    }

    [Fact]
    public void All_of_unlock_prunes_entire_group_when_required_child_cycles()
    {
        var guide = new CompiledGuideBuilder()
            .AddItem("item:root")
            .AddCharacter("char:locked")
            .AddQuest("quest:cyclic", dbName: "CYCLIC", requiredItems: new[] { ("item:root", 1) })
            .AddQuest("quest:viable", dbName: "VIABLE")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:root", 1) })
            .AddItemSource(
                "item:root",
                "char:locked",
                edgeType: (byte)EdgeType.DropsItem,
                sourceType: (byte)NodeType.Character
            )
            .AddUnlockPredicate("char:locked", "quest:cyclic")
            .AddUnlockPredicate("char:locked", "quest:viable")
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var rootItem = projector
            .GetRootChildren(rootQuestIndex)
            .Single(child => child.Label == "Collect: item:root");

        Assert.DoesNotContain(
            projector.GetChildren(rootItem),
            child => child.Label == "Drops from: char:locked"
        );
    }

    [Fact]
    public void Keyword_talk_completion_uses_talk_label()
    {
        var guide = AdventureGuide.CompiledGuide.CompiledGuideLoader.ParseJson(
            """
            {
                "nodes": [
                    {"node_id":0,"key":"quest:meetbassle","node_type":0,"display_name":"Meet the Fisherman","scene":null,"x":null,"y":null,"z":null,"flags":0,"level":0,"zone_key":null,"db_name":"ROOT","description":null,"keyword":null,"zone_display":null,"xp_reward":0,"gold_reward":0,"reward_item_key":null,"disabled_text":null,"key_item_key":null,"destination_zone_key":null,"destination_display":null},
                    {"node_id":1,"key":"char:bassle","node_type":2,"display_name":"Bassle Wavebreaker","scene":"Town","x":10.0,"y":20.0,"z":30.0,"flags":0,"level":0,"zone_key":null,"db_name":null,"description":null,"keyword":null,"zone_display":null,"xp_reward":0,"gold_reward":0,"reward_item_key":null,"disabled_text":null,"key_item_key":null,"destination_zone_key":null,"destination_display":null}
                ],
                "edges": [],
                "forward_adjacency": [[],[]],
                "reverse_adjacency": [[],[]],
                "quest_node_ids": [0],
                "item_node_ids": [],
                "quest_specs": [
                    {"quest_id":0,"quest_index":0,"prereq_quest_ids":[],"prereq_quest_indices":[],"required_items":[],"steps":[],"giver_node_ids":[],"completer_node_ids":[1],"chains_to_ids":[],"is_implicit":false,"is_infeasible":false,"display_name":"Meet the Fisherman"}
                ],
                "item_sources": [],
                "unlock_predicates": [],
                "topo_order": [0],
                "item_to_quest_indices": [],
                "quest_to_dependent_quest_indices": [[]],
                "zone_node_ids": [],
                "zone_adjacency": [],

                "giver_blueprints": [],
                "completion_blueprints": [
                    {"quest_id":0,"character_id":1,"position_id":1,"interaction_type":1,"keyword":"taking"}
                ],
                "infeasible_node_ids": []
            }
            """
        );
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(
            Array.Empty<string>(),
            new[] { "ROOT" },
            new Dictionary<string, int>(),
            Array.Empty<string>()
        );
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = ResolutionTestFactory
            .BuildSpecTreeProjector(guide, tracker, currentSceneProvider: () => string.Empty)
            .Projector;

        var completerRef = projector
            .GetRootChildren(0)
            .Single(r => r.Kind == SpecTreeKind.Completer);
        Assert.Equal("Talk to Bassle Wavebreaker — say \"taking\"", completerRef.Label);
    }
}
