using AdventureGuide.CompiledGuide;
using AdventureGuide.Graph;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class ItemSourceVisibilityPolicyTests
{
	private static (CompiledGuide.CompiledGuide Guide, int ItemIndex) BuildItemGuide(
		params (string SourceKey, bool IsFriendly, EdgeType EdgeType)[] sources
	)
	{
		var builder = new CompiledGuideBuilder().AddItem("item:target");
		foreach (var (sourceKey, isFriendly, edgeType) in sources)
		{
			builder = builder
				.AddCharacter(sourceKey, scene: "Forest", x: 0f, y: 0f, z: 0f, isFriendly: isFriendly)
				.AddItemSource("item:target", sourceKey, edgeType: (byte)edgeType);
		}
		var guide = builder.Build();
		int itemIndex = 0;
		for (int i = 0; i < guide.ItemCount; i++)
		{
			if (string.Equals(guide.GetNodeKey(guide.ItemNodeId(i)), "item:target", StringComparison.Ordinal))
			{
				itemIndex = i;
				break;
			}
		}
		return (guide, itemIndex);
	}

	private static List<string> FilterSourceKeys(CompiledGuide.CompiledGuide guide, int itemIndex)
	{
		var visible = new List<SourceSiteEntry>();
		ItemSourceVisibilityPolicy.Filter(guide.GetItemSources(itemIndex), guide, visible);
		var keys = new List<string>();
		foreach (var source in visible)
			keys.Add(guide.GetNodeKey(source.SourceId));
		return keys;
	}

	[Fact]
	public void HostileDrops_SuppressFriendlyDrops()
	{
		var (guide, itemIndex) = BuildItemGuide(
			("npc:wolf", false, EdgeType.DropsItem),
			("npc:farmer", true, EdgeType.DropsItem),
			("npc:trader", true, EdgeType.SellsItem)
		);

		var keys = FilterSourceKeys(guide, itemIndex);

		Assert.Contains("npc:wolf", keys);
		Assert.DoesNotContain("npc:farmer", keys);
		Assert.Contains("npc:trader", keys);
	}

	[Fact]
	public void NoHostileDrops_KeepsAllSources()
	{
		var (guide, itemIndex) = BuildItemGuide(
			("npc:farmer", true, EdgeType.DropsItem),
			("npc:trader", true, EdgeType.SellsItem),
			("npc:questgiver", true, EdgeType.GivesItem)
		);

		var keys = FilterSourceKeys(guide, itemIndex);

		Assert.Equal(3, keys.Count);
		Assert.Contains("npc:farmer", keys);
		Assert.Contains("npc:trader", keys);
		Assert.Contains("npc:questgiver", keys);
	}

	[Fact]
	public void NonDropSources_NeverSuppressed()
	{
		var (guide, itemIndex) = BuildItemGuide(
			("npc:wolf", false, EdgeType.DropsItem),
			("npc:trader", true, EdgeType.SellsItem),
			("npc:questgiver", true, EdgeType.GivesItem)
		);

		var keys = FilterSourceKeys(guide, itemIndex);

		Assert.Contains("npc:trader", keys);
		Assert.Contains("npc:questgiver", keys);
	}

	[Fact]
	public void Filter_ReusesProvidedList()
	{
		// Canonical allocation pattern: caller owns the list, Filter clears
		// and writes. Calling twice with the same list must yield consistent
		// output without carrying over entries from the first call.
		var (guide, itemIndex) = BuildItemGuide(
			("npc:wolf", false, EdgeType.DropsItem),
			("npc:farmer", true, EdgeType.DropsItem)
		);

		var visible = new List<SourceSiteEntry>();
		ItemSourceVisibilityPolicy.Filter(guide.GetItemSources(itemIndex), guide, visible);
		int firstCount = visible.Count;

		// Same list, same data — must not accumulate.
		ItemSourceVisibilityPolicy.Filter(guide.GetItemSources(itemIndex), guide, visible);
		Assert.Equal(firstCount, visible.Count);
	}
}
