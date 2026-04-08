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
    public void Root_children_include_prereqs_givers_items_steps_and_completers()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:pre", dbName: "PRE")
            .AddItem("item:gem")
            .AddCharacter("char:giver")
            .AddCharacter("char:turnin")
            .AddQuest(
                "quest:root",
                dbName: "ROOT",
                prereqs: new[] { "quest:pre" },
                givers: new[] { "char:giver" },
                completers: new[] { "char:turnin" },
                requiredItems: new[] { ("item:gem", 2) })
            .Build();
        var tracker = new QuestPhaseTracker(guide);
        tracker.Initialize(Array.Empty<string>(), Array.Empty<string>(), new Dictionary<string, int>(), Array.Empty<string>());
        var projector = new SpecTreeProjector(guide, tracker, new UnlockPredicateEvaluator(guide, tracker));

        int rootQuestIndex = FindQuestIndex(guide, "quest:root");
        var roots = projector.GetRootChildren(rootQuestIndex);

        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Prerequisite && r.DisplayName == "quest:pre");
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Giver && r.DisplayName == "char:giver");
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Item && r.DisplayName == "item:gem" && !r.IsCompleted);
        Assert.Contains(roots, r => r.Kind == SpecTreeKind.Completer && r.DisplayName == "char:turnin");
    }

    [Fact]
    public void Item_children_project_sources_and_blocked_state()
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
        var children = projector.GetChildren(itemRoot);

        Assert.Single(children);
        Assert.Equal(SpecTreeKind.Source, children[0].Kind);
        Assert.Equal("char:wolf", children[0].DisplayName);
        Assert.True(children[0].IsBlocked);
    }
}
