using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class ZoneLineTextTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" ")]
    public void Unknown_gate_never_claims_an_empty_quest_requirement(string? reason)
    {
        var text = ZoneLineText.Format("Vitheo's Plane", true, reason);
        Assert.Contains("Route locked", text);
        Assert.DoesNotContain("Complete", text);
    }

    [Fact]
    public void Known_quest_gate_is_removed_after_unlock()
    {
        Assert.Contains(
            "Requires: Complete \"Soluna\"",
            ZoneLineText.Format("Soluna", true, "Soluna")
        );
        Assert.DoesNotContain("Requires", ZoneLineText.Format("Soluna", false, "Soluna"));
        Assert.DoesNotContain("locked", ZoneLineText.Format("Soluna", false, null));
    }
}
