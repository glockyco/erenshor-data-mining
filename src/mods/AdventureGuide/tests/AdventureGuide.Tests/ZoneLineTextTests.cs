using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class ZoneLineTextTests
{
    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData(" ")]
    public void Unknown_gate_never_claims_an_empty_requirement(string? reason)
    {
        var text = ZoneLineText.Format("Vitheo's Plane", true, reason);
        Assert.Contains("Route locked", text);
        Assert.DoesNotContain("Complete", text);
    }

    [Fact]
    public void Known_gate_description_is_removed_after_unlock()
    {
        Assert.Equal(
            "To: Soluna\nRequires Ghostly Key",
            ZoneLineText.Format("Soluna", true, "Requires Ghostly Key")
        );
        Assert.DoesNotContain(
            "Requires",
            ZoneLineText.Format("Soluna", false, "Requires Ghostly Key")
        );
        Assert.DoesNotContain("locked", ZoneLineText.Format("Soluna", false, null));
    }
}
