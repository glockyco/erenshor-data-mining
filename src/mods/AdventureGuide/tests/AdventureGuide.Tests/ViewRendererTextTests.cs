using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ViewRendererTextTests
{
    private static Node Entity(string key, NodeType type, string displayName) =>
        new()
        {
            Key = key,
            Type = type,
            DisplayName = displayName,
        };

    [Fact]
    public void FormatCompletion_ItemTarget_UsesReadVerb()
    {
        var item = Entity("item:torn-note", NodeType.Item, "Torn Note");

        string label = ViewRenderer.FormatCompletion(item, keyword: null);

        Assert.Equal("Read: Torn Note", label);
    }

    [Fact]
    public void FormatCompletion_CharacterTarget_KeepsTurnInText()
    {
        var character = Entity("character:lucian", NodeType.Character, "Lucian Revald");

        string label = ViewRenderer.FormatCompletion(character, "open sesame");

        Assert.Equal("Turn in to Lucian Revald — say \"open sesame\"", label);
    }

    [Fact]
    public void FormatCompletion_QuestTarget_UsesCompleteVerb()
    {
        var quest = Entity("quest:wyland-note", NodeType.Quest, "Wyland's Note");

        string label = ViewRenderer.FormatCompletion(quest, keyword: null);

        Assert.Equal("Complete: Wyland's Note", label);
    }

    [Fact]
    public void GetCompletionFallbackNotice_NoCompletionEdges_ReturnsScriptedNotice()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:root", "Root Quest", dbName: "RootQuest")
            .Build();
        var quest = graph.GetNode("quest:root")!;

        string? notice = ViewRenderer.GetCompletionFallbackNotice(graph, quest);

        Assert.Equal(
            "Completion method not in guide data. Quest may be scripted or not yet completable.",
            notice);
    }

    [Fact]
    public void GetCompletionFallbackNotice_WithCompletionEdges_ReturnsNull()
    {
        var graph = new TestGraphBuilder()
            .AddQuest("quest:root", "Root Quest", dbName: "RootQuest")
            .AddCharacter("character:turnin", "Turn In")
            .AddEdge("quest:root", "character:turnin", EdgeType.CompletedBy)
            .Build();
        var quest = graph.GetNode("quest:root")!;

        string? notice = ViewRenderer.GetCompletionFallbackNotice(graph, quest);

        Assert.Null(notice);
    }
}
