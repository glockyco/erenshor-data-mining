using AdventureGuide.Data;

namespace AdventureGuide.Tests;

public sealed class RespawnIdentityTests
{
    [Theory]
    [InlineData("character:brackish crocodile whelp:1", "character:brackish crocodile whelp")]
    [InlineData("character:sivakayan raider:12", "character:sivakayan raider")]
    [InlineData("character:arenachest 1", "character:arenachest 1")]
    [InlineData("character:source:Hidden", "character:source:Hidden")]
    [InlineData("character:source:", "character:source:")]
    [InlineData("character:1", "character:1")]
    public void Respawn_query_uses_runtime_prefab_identity(string query, string runtimeKey) =>
        Assert.Equal(runtimeKey, CharacterStableKey.Normalize(query));
}
