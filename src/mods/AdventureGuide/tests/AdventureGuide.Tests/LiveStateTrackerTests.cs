using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class LiveStateTrackerTests
{
	[Fact]
	public void FindBestPositionMatchIndex_PrefersSharedPositionKeyOverCloserNeighbor()
	{
		var target = (206.9901f, 13.68f, 425.08f);
		(float X, float Y, float Z)[] candidates =
		[
			(206.9990f, 13.68f, 425.08f),
			(206.9899f, 13.68f, 425.08f),
		];

		int index = LiveStateTracker.FindBestPositionMatchIndex(target, candidates);

		Assert.Equal(0, index);
	}

	[Fact]
	public void FindBestPositionMatchIndex_FallsBackToNearestWhenNoSharedPositionKeyExists()
	{
		var target = (100.00f, 5.00f, 200.00f);
		(float X, float Y, float Z)[] candidates =
		[
			(101.50f, 5.00f, 200.00f),
			(100.40f, 5.00f, 200.00f),
		];

		int index = LiveStateTracker.FindBestPositionMatchIndex(target, candidates);

		Assert.Equal(1, index);
	}

	[Fact]
	public void FindBestPositionMatchIndex_ReturnsNegativeOneWhenNothingIsCloseEnough()
	{
		var target = (100.00f, 5.00f, 200.00f);
		(float X, float Y, float Z)[] candidates = [(103.50f, 5.00f, 200.00f)];

		int index = LiveStateTracker.FindBestPositionMatchIndex(target, candidates);

		Assert.Equal(-1, index);
	}
}
