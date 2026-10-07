using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class ZoneLineAlternativeLabelsTests
{
    [Fact]
    public void Stationary_and_submetre_updates_reuse_labels()
    {
        var labels = new ZoneLineAlternativeLabels(2);
        var header = labels.Header(2);
        Assert.Same(header, labels.Header(2));
        var row = labels.Row(0, "Stowaway", 120.1f);
        var selectable = row.Selectable;
        var text = row.Text;
        var tip = row.Tooltip;
        var req = row.Requirement("A quest", "QUEST");
        labels.Row(0, "Stowaway", 120.4f);
        Assert.Same(selectable, row.Selectable);
        Assert.Same(text, row.Text);
        Assert.Same(tip, row.Tooltip);
        Assert.Same(req, row.Requirement("A quest", "QUEST"));
    }

    [Fact]
    public void Distance_destination_and_count_changes_refresh_only_affected_labels()
    {
        var labels = new ZoneLineAlternativeLabels(2);
        var row = labels.Row(0, "Stowaway", 120);
        var tip = row.Tooltip;
        labels.Row(0, "Stowaway", 121);
        Assert.Equal("To Stowaway (121m)", row.Text);
        Assert.EndsWith("###zl_2_0", row.Selectable);
        Assert.Same(tip, row.Tooltip);
        labels.Row(0, "Hidden", 121);
        Assert.Equal("To Hidden (121m)", row.Text);
        Assert.Equal("Route via Hidden", row.Tooltip);
        Assert.EndsWith("###zl_2_0", row.Selectable);
        Assert.EndsWith("###zl_2_1", labels.Row(1, "Hidden", 121).Selectable);
        Assert.StartsWith("2 zone connections", labels.Header(2));
        Assert.StartsWith("3 zone connections", labels.Header(3));
    }
}
