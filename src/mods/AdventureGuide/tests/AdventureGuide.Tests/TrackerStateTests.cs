using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class TrackerStateTests
{
	[Fact]
	public void DrainPendingFacts_IsEmpty_ForUnmutatedState()
	{
		var state = new TrackerState();

		var facts = state.DrainPendingFacts();

		Assert.Empty(facts);
	}

	[Fact]
	public void DrainPendingFacts_EmitsTrackerSetWildcard_AfterTrack()
	{
		var state = new TrackerState();

		state.Track("QUESTA");

		Assert.Contains(new FactKey(FactKind.TrackerSet, "*"), state.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_EmitsTrackerSetWildcard_AfterUntrack()
	{
		var state = new TrackerState();
		state.Track("QUESTA");
		state.DrainPendingFacts();

		state.Untrack("QUESTA");

		Assert.Contains(new FactKey(FactKind.TrackerSet, "*"), state.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_Suppresses_WhenTrackIsNoOp()
	{
		var state = new TrackerState();
		state.Track("QUESTA");
		state.DrainPendingFacts();

		state.Track("QUESTA");

		Assert.Empty(state.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_Suppresses_WhenUntrackIsNoOp()
	{
		var state = new TrackerState();

		state.Untrack("QUESTA");

		Assert.Empty(state.DrainPendingFacts());
	}

	[Fact]
	public void DrainPendingFacts_ClearsFlag_AfterFirstDrain()
	{
		var state = new TrackerState();
		state.Track("QUESTA");

		var first = state.DrainPendingFacts();
		var second = state.DrainPendingFacts();

		Assert.NotEmpty(first);
		Assert.Empty(second);
	}

	[Fact]
	public void DrainPendingFacts_Coalesces_MultipleMutationsIntoSingleWildcard()
	{
		var state = new TrackerState();

		state.Track("QUESTA");
		state.Track("QUESTB");
		state.Untrack("QUESTA");

		var facts = state.DrainPendingFacts();
		Assert.Single(facts);
		Assert.Contains(new FactKey(FactKind.TrackerSet, "*"), facts);
	}

	[Fact]
	public void DrainPendingFacts_IsUnaffected_ByOnStepAdvanced()
	{
		var state = new TrackerState();
		state.Track("QUESTA");
		state.DrainPendingFacts();

		state.OnStepAdvanced("QUESTA");

		Assert.Empty(state.DrainPendingFacts());
	}
}
