using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class InventoryCountPolicyTests
{
    [Fact]
    public void GeneralStacksAccumulateAcrossSlotsWithoutMixingItems()
    {
        var counts = new Dictionary<string, int>();
        InventoryCountPolicy.Add(counts, "item:bones", true, 18);
        InventoryCountPolicy.Add(counts, "item:bones", true, 4);
        InventoryCountPolicy.Add(counts, "item:coal", true, 2);
        Assert.Equal(22, counts["item:bones"]);
        Assert.Equal(2, counts["item:coal"]);
    }

    [Theory]
    [InlineData(1)]
    [InlineData(3)]
    [InlineData(15)]
    public void EquipmentCountsPiecesNotQuality(int quality)
    {
        var counts = new Dictionary<string, int>();
        InventoryCountPolicy.Add(counts, "item:sword", false, quality);
        InventoryCountPolicy.Add(counts, "item:sword", false, quality);
        Assert.Equal(2, counts["item:sword"]);
    }

    [Fact]
    public void ZeroGeneralQuantityDoesNotInventAnItem()
    {
        var counts = new Dictionary<string, int>();
        InventoryCountPolicy.Add(counts, "item:bones", true, 0);
        Assert.Equal(0, counts["item:bones"]);
    }
}
