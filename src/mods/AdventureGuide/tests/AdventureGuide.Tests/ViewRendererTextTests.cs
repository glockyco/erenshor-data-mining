using AdventureGuide.Graph;
using AdventureGuide.Tests.Helpers;
using AdventureGuide.UI;
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
}
