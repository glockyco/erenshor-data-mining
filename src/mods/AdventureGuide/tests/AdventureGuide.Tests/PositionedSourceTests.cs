using System.Globalization;
using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class PositionedSourceTests
{
    [Theory]
    [InlineData("mining:hidden:-1.25:2:3", "mining")]
    [InlineData("water:Stowaway:-1.25:2:3", "water")]
    [InlineData("itembag:Hidden:-1.25:2:3", "itembag")]
    public void Coordinates_are_invariant_and_keep_scene_and_kind(string key, string kind)
    {
        var previous = CultureInfo.CurrentCulture;
        try
        {
            CultureInfo.CurrentCulture = CultureInfo.GetCultureInfo("de-DE");
            Assert.True(PositionedSource.TryParse(key, out var parsed));
            Assert.Equal(kind, parsed.Kind);
            Assert.Equal(key.Split(':')[1], parsed.Scene);
            Assert.Equal(-1.25f, parsed.X);
            Assert.Equal(2f, parsed.Y);
            Assert.Equal(3f, parsed.Z);
        }
        finally
        {
            CultureInfo.CurrentCulture = previous;
        }
    }

    [Theory]
    [InlineData("mining:hidden:1:2:3", false)]
    [InlineData("itembag:hidden:1:2:3", false)]
    [InlineData("water:saltedstrand:-7351.00:-53.00:-7277.75", true)]
    public void Only_water_sources_lack_a_destination(string key, bool zoneWide)
    {
        // Water keys name a water volume's center, which can lie off the map.
        Assert.True(PositionedSource.TryParse(key, out var parsed));
        Assert.Equal(zoneWide, parsed.IsZoneWide);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("mining::1:2:3")]
    [InlineData("mining:Hidden:1:2")]
    [InlineData("mining:Hidden:NaN:2:3")]
    [InlineData("mining:Hidden:1:2:Infinity")]
    [InlineData("water:Hidden:1:2:3:4")]
    [InlineData("fishing:Hidden")]
    [InlineData("mining-nodes:Hidden")]
    [InlineData("character:test:1:2:3")]
    public void Invalid_and_obsolete_keys_are_not_positioned_sources(string? key) =>
        Assert.False(PositionedSource.TryParse(key, out _));
}
