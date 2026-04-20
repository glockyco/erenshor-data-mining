using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.Position.Resolvers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class LiveStateBackedPositionResolverTests
{
	[Fact]
	public void MiningNode_UsesCachedAvailability()
	{
		var probe = new ResolverProbe(cachedAvailability: false, liveAvailability: true);
		var resolver = probe.Build();
		var results = new List<ResolvedPosition>();

		resolver.Resolve(
			new Node
			{
				Key = "node:mining",
				Type = NodeType.MiningNode,
				X = 10f,
				Y = 20f,
				Z = 30f,
				Scene = "Forest"
			},
			results
		);

		Assert.Single(results);
		Assert.False(results[0].IsActionable);
		Assert.Equal(0, probe.LiveQueryCount);
	}

	[Fact]
	public void ItemBag_UsesCachedAvailability()
	{
		var probe = new ResolverProbe(cachedAvailability: true, liveAvailability: false);
		var resolver = probe.Build();
		var results = new List<ResolvedPosition>();

		resolver.Resolve(
			new Node
			{
				Key = "bag:forest",
				Type = NodeType.ItemBag,
				X = 1f,
				Y = 2f,
				Z = 3f,
				Scene = "Forest"
			},
			results
		);

		Assert.Single(results);
		Assert.True(results[0].IsActionable);
		Assert.Equal(0, probe.LiveQueryCount);
	}

	[Fact]
	public void MiningNode_FallsBackToLiveQuery()
	{
		var probe = new ResolverProbe(cachedAvailability: null, liveAvailability: true);
		var resolver = probe.Build();
		var results = new List<ResolvedPosition>();

		resolver.Resolve(
			new Node
			{
				Key = "node:mining",
				Type = NodeType.MiningNode,
				X = 10f,
				Y = 20f,
				Z = 30f,
				Scene = "Forest"
			},
			results
		);

		Assert.Single(results);
		Assert.True(results[0].IsActionable);
		Assert.Equal(1, probe.LiveQueryCount);
	}

	[Fact]
	public void MissingCoordinates_EmitsNothing()
	{
		var probe = new ResolverProbe(cachedAvailability: true, liveAvailability: true);
		var resolver = probe.Build();
		var results = new List<ResolvedPosition>();

		resolver.Resolve(
			new Node
			{
				Key = "bag:missing",
				Type = NodeType.ItemBag,
				Scene = "Forest"
			},
			results
		);

		Assert.Empty(results);
		Assert.Equal(0, probe.LiveQueryCount);
	}

	private sealed class ResolverProbe
	{
		private readonly bool? _cachedAvailability;
		private readonly bool _liveAvailability;

		public ResolverProbe(bool? cachedAvailability, bool liveAvailability)
		{
			_cachedAvailability = cachedAvailability;
			_liveAvailability = liveAvailability;
		}

		public int LiveQueryCount { get; private set; }

		public LiveStateBackedPositionResolver Build() =>
			new(
				tryGetCachedAvailability: _ => _cachedAvailability,
				queryLiveAvailability: _ =>
				{
					LiveQueryCount++;
					return _liveAvailability;
				}
			);
	}
}
