using AdventureGuide.Graph;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class LiveSceneScopeTests
{
    [Fact]
    public void CharacterHasCurrentScenePresence_ReturnsTrueWhenCharacterSceneMatches()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("character:faerie drone", scene: "Brake")
            .Build();

        var character = guide.GetNode("character:faerie drone")!;

        Assert.True(LiveSceneScope.CharacterHasCurrentScenePresence(guide, character, "Brake"));
        Assert.False(LiveSceneScope.CharacterHasCurrentScenePresence(guide, character, "Stowaway"));
    }

    [Fact]
    public void CharacterHasCurrentScenePresence_ReturnsTrueWhenAnySpawnMatchesCurrentScene()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("character:faerie drone")
            .AddSpawnPoint("spawn:brake", scene: "Brake")
            .AddSpawnPoint("spawn:stowaway", scene: "Stowaway")
            .AddEdge("character:faerie drone", "spawn:brake", EdgeType.HasSpawn)
            .AddEdge("character:faerie drone", "spawn:stowaway", EdgeType.HasSpawn)
            .Build();

        var character = guide.GetNode("character:faerie drone")!;

        Assert.True(LiveSceneScope.CharacterHasCurrentScenePresence(guide, character, "Stowaway"));
    }

    [Fact]
    public void CharacterHasCurrentScenePresence_ReturnsFalseWhenAllSpawnsAreOffScene()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("character:faerie drone")
            .AddSpawnPoint("spawn:brake:a", scene: "Brake")
            .AddSpawnPoint("spawn:brake:b", scene: "Brake")
            .AddEdge("character:faerie drone", "spawn:brake:a", EdgeType.HasSpawn)
            .AddEdge("character:faerie drone", "spawn:brake:b", EdgeType.HasSpawn)
            .Build();

        var character = guide.GetNode("character:faerie drone")!;

        Assert.False(LiveSceneScope.CharacterHasCurrentScenePresence(guide, character, "Stowaway"));
    }

    [Fact]
    public void ResolveSpawnLookupName_PrefersParentCharacterName()
    {
        var spawnNode = new Node
        {
            Key = "spawn:brake:126.97:22.02:87.10",
            DisplayName = "A Brittle Skeleton",
        };
        var parentCharacter = new Node
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
        var spawnNode = new Node
        {
            Key = "spawn:brake:126.97:22.02:87.10",
            DisplayName = "A Brittle Skeleton",
        };

        string resolved = LiveSceneScope.ResolveSpawnLookupName(spawnNode, parentCharacter: null);

        Assert.Equal("A Brittle Skeleton", resolved);
    }
}
