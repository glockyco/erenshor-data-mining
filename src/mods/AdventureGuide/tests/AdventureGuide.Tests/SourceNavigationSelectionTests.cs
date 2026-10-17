using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class SourceNavigationSelectionTests
{
    private static ItemSource Fish(string scene) =>
        new()
        {
            Type = "fishing",
            Name = "Fish",
            Scene = scene,
            Zone = scene,
        };

    private static QuestStep Collect(int order, params ItemSource[] sources) =>
        new()
        {
            Order = order,
            Action = "collect",
            TargetType = "item",
            TargetKey = "item:fish",
            TargetName = "Fish",
            Sources = [.. sources],
        };

    private static QuestEntry Quest(string name, params QuestStep[] steps) =>
        new()
        {
            StableKey = "quest:" + name,
            DBName = name,
            Steps = [.. steps],
        };

    private static (RequirementResolver resolver, ZoneGraph graph) Resolver(
        GateTestFacts? facts = null,
        List<List<List<GateAtom>>>? conditions = null,
        Dictionary<string, GateItem>? items = null
    )
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 8,
                Encounters = TestData.EmptyEncounters(),
                Quests = [],
                Conditions = conditions,
                GateItems = items,
                ZoneLookup = new()
                {
                    ["A"] = new ZoneInfo { StableKey = "zone:a", DisplayName = "A" },
                    ["B"] = new ZoneInfo { StableKey = "zone:b", DisplayName = "B" },
                    ["C"] = new ZoneInfo { StableKey = "zone:c", DisplayName = "C" },
                },
                ZoneLines =
                [
                    new() { Scene = "A", DestinationZoneKey = "zone:b" },
                    new() { Scene = "B", DestinationZoneKey = "zone:a" },
                    new() { Scene = "A", DestinationZoneKey = "zone:c" },
                    new() { Scene = "C", DestinationZoneKey = "zone:a" },
                ],
            }
        );
        var gates = new GateConditions(data, facts ?? new GateTestFacts());
        var graph = new ZoneGraph(data, gates);
        return (new RequirementResolver(data, gates, graph, q => q.Steps?.FirstOrDefault()), graph);
    }

    [Fact]
    public void Inactive_navigation_can_choose_specific_source_and_choose_it_again()
    {
        var local = Fish("A");
        var chosen = Fish("B");
        var step = Collect(1, local, chosen);
        var quest = Quest("Fishing", step);
        var selection = new SourceNavigationSelection();
        var (resolver, _) = Resolver();

        Assert.True(selection.Select(chosen, step, quest));
        var first = selection.Resolve(resolver, quest, step, "A");
        Assert.True(first.CanNavigate, first.Message);
        Assert.Equal("B", first.SelectedScene);
        Assert.Same(chosen, Assert.Single(first.Step.Sources!));

        Assert.True(selection.Select(chosen, step, quest));
        var again = selection.Resolve(resolver, quest, step, "A");
        Assert.True(again.CanNavigate, again.Message);
        Assert.Equal("B", again.SelectedScene);
        Assert.Same(chosen, Assert.Single(again.Step.Sources!));
    }

    [Fact]
    public void Source_objective_and_scene_changes_use_the_current_choice()
    {
        var a = Fish("A");
        var b = Fish("B");
        var c = Fish("C");
        var first = Collect(1, a, b);
        var second = Collect(2, a, c);
        var quest = Quest("Fishing", first, second);
        var selection = new SourceNavigationSelection();
        var (resolver, _) = Resolver();

        Assert.True(selection.Select(b, first, quest));
        Assert.Equal("B", selection.Resolve(resolver, quest, first, "A").SelectedScene);
        Assert.Equal("B", selection.Resolve(resolver, quest, first, "B").SelectedScene);
        Assert.True(selection.Select(a, first, quest));
        Assert.Equal("A", selection.Resolve(resolver, quest, first, "B").SelectedScene);
        Assert.True(selection.Select(c, second, quest));
        var next = selection.Resolve(resolver, quest, second, "B");
        Assert.True(next.CanNavigate, next.Message);
        Assert.Equal("C", next.SelectedScene);
        Assert.Equal(2, next.Step.Order);
        Assert.Same(c, Assert.Single(next.Step.Sources!));
        Assert.False(selection.Select(b, second, quest));
        Assert.Equal("C", selection.Resolve(resolver, quest, second, "C").SelectedScene);
    }

    [Fact]
    public void Gated_chosen_leaf_follows_ancestor_requirement_then_returns_to_original_choice()
    {
        var chosen = Fish("B");
        var free = Fish("A");
        var sourceGroup = new ItemSource
        {
            Type = "item_use",
            Condition = 0,
            Children = [chosen],
        };
        var step = Collect(1, free, sourceGroup);
        var quest = Quest("Gated fishing", step);
        var keySource = new ItemSource
        {
            Type = "vendor",
            Name = "Key seller",
            Scene = "A",
        };
        var facts = new GateTestFacts();
        var (resolver, graph) = Resolver(
            facts,
            [
                [
                    [new GateAtom { Kind = GateAtomKind.ItemHeld, Ref = "item:key" }],
                ],
            ],
            new()
            {
                ["item:key"] = new GateItem { Name = "Key", Sources = [keySource] },
            }
        );
        var selection = new SourceNavigationSelection();

        Assert.True(selection.Select(chosen, step, quest));
        var locked = selection.Resolve(resolver, quest, step, "A");
        Assert.True(locked.CanNavigate, locked.Message);
        Assert.Equal("item:key", locked.Step.TargetKey);
        Assert.Same(keySource, Assert.Single(locked.Step.Sources!));
        Assert.Contains(
            locked.Chain,
            link => link.Atom is { Kind: GateAtomKind.ItemHeld, Ref: "item:key" }
        );

        facts.Inventory["item:key"] = 1;
        graph.Rebuild();
        var available = selection.Resolve(resolver, quest, step, "A");
        Assert.True(available.CanNavigate, available.Message);
        Assert.Equal("item:fish", available.Step.TargetKey);
        Assert.Equal("B", available.SelectedScene);
        Assert.Same(chosen, Assert.Single(available.Step.Sources!));
        Assert.DoesNotContain(available.Step.Sources!, source => ReferenceEquals(source, free));
    }

    [Fact]
    public void Old_objective_choice_cannot_constrain_another_quest_and_clear_restores_all_sources()
    {
        var a = Fish("A");
        var b = Fish("B");
        var oldStep = Collect(1, a, b);
        var oldQuest = Quest("Old", oldStep);
        var currentStep = Collect(1, Fish("C"));
        var currentQuest = Quest("Current", currentStep);
        var selection = new SourceNavigationSelection();
        var (resolver, _) = Resolver();

        Assert.True(selection.Select(b, oldStep, oldQuest));
        var current = selection.Resolve(resolver, currentQuest, currentStep, "C");
        Assert.True(current.CanNavigate, current.Message);
        Assert.Same(currentStep, current.Step);
        Assert.Equal("C", Assert.Single(current.Step.Sources!).Scene);
        selection.Clear();
        var automatic = selection.Resolve(resolver, oldQuest, oldStep, "A");
        Assert.True(automatic.CanNavigate, automatic.Message);
        Assert.Same(oldStep, automatic.Step);
        Assert.Equal(2, automatic.Step.Sources!.Count);
    }
}
