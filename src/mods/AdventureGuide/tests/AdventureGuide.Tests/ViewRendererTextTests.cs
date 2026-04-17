using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI;
using AdventureGuide.UI.Tree;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ViewRendererTextTests
{
    [Fact]
    public void GetCompletionFallbackNotice_NoCompletionEdges_ReturnsScriptedNotice()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:root", dbName: "RootQuest")
            .Build();
        var quest = guide.GetNode("quest:root")!;

        string? notice = ViewRenderer.GetCompletionFallbackNotice(guide, quest);

        Assert.Equal(
            "Completion method not in guide data. Quest may be scripted or not yet completable.",
            notice);
    }

    [Fact]
    public void GetCompletionFallbackNotice_WithCompletionEdges_ReturnsNull()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:root", dbName: "RootQuest")
            .AddCharacter("character:turnin")
            .AddEdge("quest:root", "character:turnin", EdgeType.CompletedBy)
            .Build();
        var quest = guide.GetNode("quest:root")!;

        string? notice = ViewRenderer.GetCompletionFallbackNotice(guide, quest);

        Assert.Null(notice);
    }

    [Fact]
    public void BuildDetailSections_SplitsAcceptObjectivesAndTurnInGroups()
    {
        var roots = new SpecTreeRef[]
        {
            new(1, SpecTreeKind.Giver, 0, "Torn Note", "Read Torn Note", false, false),
            new(2, SpecTreeKind.Giver, 0, "Marching Orders", "Read Marching Orders", false, false),
            new(3, SpecTreeKind.Item, 0, "Torn Note", "Collect: Torn Note", false, false),
            new(4, SpecTreeKind.Step, 0, "Ritual", "Talk to Elder Brother", false, false),
            new(5, SpecTreeKind.Completer, 0, "Lucian Revald", "Turn in to Lucian Revald", false, false),
            new(6, SpecTreeKind.Completer, 0, "Lucian Revald", "Turn in to Lucian Revald", false, true),
        };

        var sections = ViewRenderer.BuildDetailSections(roots);

        Assert.Collection(
            sections,
            section =>
            {
                Assert.Equal("Accept", section.Label);
                Assert.True(section.ShowAlternativesLabel);
                Assert.Equal(2, section.Roots.Count);
            },
            section =>
            {
                Assert.Equal("Objectives", section.Label);
                Assert.False(section.ShowAlternativesLabel);
                Assert.Equal(2, section.Roots.Count);
            },
            section =>
            {
                Assert.Equal("Turn in", section.Label);
                Assert.True(section.ShowAlternativesLabel);
                Assert.Equal(2, section.Roots.Count);
            });
    }
}
