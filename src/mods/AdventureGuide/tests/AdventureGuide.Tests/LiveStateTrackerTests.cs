using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
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

	[Fact]
	public void UpdateFrameState_DoesNotScanMiningNodes()
	{
		string source = ReadRepoFile("src/mods/AdventureGuide/src/State/LiveStateTracker.cs");
		string updateBody = ExtractBetween(
			source,
			"public ChangeSet UpdateFrameState()",
			"public SpawnInfo GetSpawnState"
		);

		Assert.DoesNotContain("foreach (var mn in _miningNodes)", updateBody);
	}

	[Fact]
	public void MiningNodePatch_CoversMineAndRespawnTransitions()
	{
		string source = ReadRepoFile("src/mods/AdventureGuide/src/Patches/MiningNodePatch.cs");

		Assert.Contains("nameof(MiningNode.Mine)", source);
		Assert.Contains("\"Update\"", source);
	}

	[Fact]
	public void UnknownSourceChange_InvalidatesWildcardSourceSubscribers()
	{
		var guide = new CompiledGuideBuilder().Build();
		var tracker = new QuestStateTracker(guide);
		var unlocks = new UnlockEvaluator(guide, new GameState(guide), tracker);
		var liveState = new LiveStateTracker(guide, unlocks);
		var method = typeof(LiveStateTracker).GetMethod(
			"BuildSourceChange",
			System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
		Assert.NotNull(method);

		var change = Assert.IsType<ChangeSet>(method!.Invoke(liveState, new object?[] { null }));

		Assert.True(change.LiveWorldChanged);
		Assert.Contains(
			change.ChangedFacts,
			fact => fact.Kind == FactKind.SourceState && fact.Key == "*");
	}

	private static string ReadRepoFile(string relativePath)
	{
		var directory = new DirectoryInfo(AppContext.BaseDirectory);
		while (directory != null && !Directory.Exists(Path.Combine(directory.FullName, ".git")))
			directory = directory.Parent;

		Assert.NotNull(directory);
		return File.ReadAllText(Path.Combine(directory!.FullName, relativePath));
	}

	private static string ExtractBetween(string content, string start, string end)
	{
		int startIndex = content.IndexOf(start, StringComparison.Ordinal);
		Assert.True(startIndex >= 0, $"Could not find '{start}'.");
		int endIndex = content.IndexOf(end, startIndex, StringComparison.Ordinal);
		Assert.True(endIndex >= 0, $"Could not find '{end}'.");
		return content[startIndex..endIndex];
	}
}
