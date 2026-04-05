using AdventureGuide.Resolution;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TargetInstanceIdentityTests
{
    [Fact]
    public void Get_UsesSourceKeyWhenPresent()
    {
        string key = TargetInstanceIdentity.Get(
            "character:islander bandit",
            "spawn:stowaway:342.23:52.52:490.37");

        Assert.Equal("spawn:stowaway:342.23:52.52:490.37", key);
    }

    [Fact]
    public void Get_FallsBackToTargetNodeKeyWhenSourceMissing()
    {
        string key = TargetInstanceIdentity.Get("character:islander bandit", null);

        Assert.Equal("character:islander bandit", key);
    }

    [Fact]
    public void BuildDedupeKey_CollapsesSharedPhysicalSourceAcrossCharacterKeys()
    {
        string first = TargetInstanceIdentity.BuildDedupeKey(
            "quest:test",
            "item:bandit note",
            "character:islander bandit",
            "Stowaway",
            "spawn:stowaway:342.23:52.52:490.37");

        string second = TargetInstanceIdentity.BuildDedupeKey(
            "quest:test",
            "item:bandit note",
            "character:islander bandit 2",
            "Stowaway",
            "spawn:stowaway:342.23:52.52:490.37");

        Assert.Equal(first, second);
    }
}
