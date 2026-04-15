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
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker));

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootQuestIndex);

        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Prerequisite && r.Label == "Requires: quest:pre");
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Giver && r.Label == "Talk to char:giver");
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Item && r.Label == "Collect: item:gem (0/2)" && !r.IsCompleted);
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Step && r.Label == "Kill: char:wolf");
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
            .AddItemSource("item:pelt", "char:wolf", edgeType: 16)
            .AddItemSource("item:pelt", "char:ranger", edgeType: 16)
            .AddItemSource("item:pelt", "char:vendor", edgeType: 17)
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:pelt", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker));

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
            .AddItemSource("item:pelt", "char:wolf")
            .AddUnlockPredicate("char:wolf", "quest:unlock")
            .AddQuest("quest:root", dbName: "ROOT", requiredItems: new[] { ("item:pelt", 1) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker));

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
            .AddItemSource("item:key", "char:enemy", edgeType: 16, sourceType: 2) // 16=DropsItem, 2=Character
            .AddUnlockPredicate("char:npc", "item:key", checkType: 1)
            .AddQuest("quest:a", dbName: "QUESTA", completers: new[] { "char:npc" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = new SpecTreeProjector(guide, tracker, evaluator);

        int questIndex = FindQuestIndex(guide, "quest:a");
        var roots = projector.GetRootChildren(questIndex);
        var completerRef = roots.Single(r => r.Kind == SpecTreeKind.Completer);
        var unlockRefs = projector.GetUnlockChildren(completerRef);

        Assert.Single(unlockRefs);
        Assert.Equal(SpecTreeKind.Item, unlockRefs[0].Kind);

        // Expanding the item ref must return its sources
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
            .AddUnlockPredicate("char:npc", "quest:gate", checkType: 0) // 0 = quest completion
            .AddQuest("quest:a", dbName: "QUESTA", completers: new[] { "char:npc" })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), new[] { "QUESTA" }, new Dictionary<string, int>(), Array.Empty<string>());
        var evaluator = new UnlockPredicateEvaluator(guide, tracker);
        var projector = new SpecTreeProjector(guide, tracker, evaluator);

        int questIndex = FindQuestIndex(guide, "quest:a");
        var roots = projector.GetRootChildren(questIndex);
        var completerRef = roots.Single(r => r.Kind == SpecTreeKind.Completer);
        var unlockRefs = projector.GetUnlockChildren(completerRef);

        Assert.Single(unlockRefs);
        Assert.Equal(SpecTreeKind.Prerequisite, unlockRefs[0].Kind);
    }
}
