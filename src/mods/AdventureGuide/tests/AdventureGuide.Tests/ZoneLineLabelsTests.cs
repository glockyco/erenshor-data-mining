using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class ZoneLineLabelsTests
{
    [Fact]
    public void Movement_changes_display_but_not_selectable_identity()
    {
        var a = ZoneLineLabels.Selectable("Stowaway", 120, 2, 0);
        var b = ZoneLineLabels.Selectable("Stowaway", 121, 2, 0);
        Assert.StartsWith("To Stowaway (120m)", a);
        Assert.StartsWith("To Stowaway (121m)", b);
        Assert.Equal(
            a[a.IndexOf("###", StringComparison.Ordinal)..],
            b[b.IndexOf("###", StringComparison.Ordinal)..]
        );
        Assert.EndsWith("###zl_2_1", ZoneLineLabels.Selectable("Stowaway", 120, 2, 1));
        Assert.EndsWith("###zl_3_0", ZoneLineLabels.Selectable("Stowaway", 120, 3, 0));
    }
}
