using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.Position.Resolvers;
using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class LiveStateBackedPositionResolverTests
{
	[Fact]
	public void MiningNode_UsesCachedAvailability()
	{
		var resolver = new RecordingResolver(cachedAvailability: false, liveAvailability: true);
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
		Assert.Equal(0, resolver.LiveQueryCount);
	}

	[Fact]
	public void ItemBag_UsesCachedAvailability()
	{
		var resolver = new RecordingResolver(cachedAvailability: true, liveAvailability: false);
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
		Assert.Equal(0, resolver.LiveQueryCount);
	}

	[Fact]
	public void MiningNode_FallsBackToLiveQuery()
	{
		var resolver = new RecordingResolver(cachedAvailability: null, liveAvailability: true);
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
		Assert.Equal(1, resolver.LiveQueryCount);
	}

	[Fact]
	public void MissingCoordinates_EmitsNothing()
	{
		var resolver = new RecordingResolver(cachedAvailability: true, liveAvailability: true);
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
		Assert.Equal(0, resolver.LiveQueryCount);
	}

	private sealed class RecordingResolver : LiveStateBackedPositionResolver
	{
		private readonly bool? _cachedAvailability;
		private readonly bool _liveAvailability;

		public RecordingResolver(bool? cachedAvailability, bool liveAvailability)
			: base(null!)
		{
			_cachedAvailability = cachedAvailability;
			_liveAvailability = liveAvailability;
		}

		public int LiveQueryCount { get; private set; }

		protected override bool? TryGetCachedAvailability(Node node) => _cachedAvailability;

		protected override bool QueryLiveAvailability(Node node)
		{
			LiveQueryCount++;
			return _liveAvailability;
		}
	}
}
