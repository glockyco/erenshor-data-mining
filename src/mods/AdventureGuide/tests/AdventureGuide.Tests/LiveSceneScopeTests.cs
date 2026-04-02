using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class LiveSceneScopeTests
{
    [Fact]
    public void CharacterHasCurrentScenePresence_ReturnsTrueWhenCharacterSceneMatches()
    {
        var graph = new TestGraphBuilder()
            .AddCharacter("character:faerie drone", "A Faerie Drone", scene: "Brake")
            .Build();

        var character = graph.GetNode("character:faerie drone")!;

        Assert.True(LiveSceneScope.CharacterHasCurrentScenePresence(graph, character, "Brake"));
        Assert.False(LiveSceneScope.CharacterHasCurrentScenePresence(graph, character, "Stowaway"));
    }

    [Fact]
    public void CharacterHasCurrentScenePresence_ReturnsTrueWhenAnySpawnMatchesCurrentScene()
    {
        var graph = new TestGraphBuilder()
            .AddCharacter("character:faerie drone", "A Faerie Drone")
            .AddSpawnPoint("spawn:brake", "Skeleton", scene: "Brake")
            .AddSpawnPoint("spawn:stowaway", "Skeleton", scene: "Stowaway")
            .AddEdge("character:faerie drone", "spawn:brake", AdventureGuide.Graph.EdgeType.HasSpawn)
            .AddEdge("character:faerie drone", "spawn:stowaway", AdventureGuide.Graph.EdgeType.HasSpawn)
            .Build();

        var character = graph.GetNode("character:faerie drone")!;

        Assert.True(LiveSceneScope.CharacterHasCurrentScenePresence(graph, character, "Stowaway"));
    }

    [Fact]
    public void CharacterHasCurrentScenePresence_ReturnsFalseWhenAllSpawnsAreOffScene()
    {
        var graph = new TestGraphBuilder()
            .AddCharacter("character:faerie drone", "A Faerie Drone")
            .AddSpawnPoint("spawn:brake:a", "A Brittle Skeleton", scene: "Brake")
            .AddSpawnPoint("spawn:brake:b", "A Brown Bear Cub", scene: "Brake")
            .AddEdge("character:faerie drone", "spawn:brake:a", AdventureGuide.Graph.EdgeType.HasSpawn)
            .AddEdge("character:faerie drone", "spawn:brake:b", AdventureGuide.Graph.EdgeType.HasSpawn)
            .Build();

        var character = graph.GetNode("character:faerie drone")!;

        Assert.False(LiveSceneScope.CharacterHasCurrentScenePresence(graph, character, "Stowaway"));
    }

    [Fact]
    public void ResolveSpawnLookupName_PrefersParentCharacterName()
    {
        var spawnNode = new AdventureGuide.Graph.Node
        {
            Key = "spawn:brake:126.97:22.02:87.10",
            DisplayName = "A Brittle Skeleton",
        };
        var parentCharacter = new AdventureGuide.Graph.Node
        {
            Key = "character:faerie drone",
            DisplayName = "A Faerie Drone",
        };

        string resolved = LiveSceneScope.ResolveSpawnLookupName(spawnNode, parentCharacter);

        Assert.Equal("A Faerie Drone", resolved);
    }

    [Fact]
    public void ResolveSpawnLookupName_FallsBackToSpawnNameWithoutParentCharacter()
    {
        var spawnNode = new AdventureGuide.Graph.Node
        {
            Key = "spawn:brake:126.97:22.02:87.10",
            DisplayName = "A Brittle Skeleton",
        };

        string resolved = LiveSceneScope.ResolveSpawnLookupName(spawnNode, parentCharacter: null);

        Assert.Equal("A Brittle Skeleton", resolved);
    }
}
