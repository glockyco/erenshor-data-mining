using AdventureGuide.Config;
using AdventureGuide.Markers;
using AdventureGuide.Resolution;
using BepInEx.Configuration;
using Xunit;

namespace AdventureGuide.Tests.Markers;

public sealed class MarkerRendererTests
{
	[Fact]
	public void RenderForTest_ShrinksPool_WhenProjectedEntryCountDropsWithSameCandidates()
	{
		var pool = new FakeMarkerPool();
		var projection = new FakeMarkerProjection();
		var renderer = new MarkerRenderer(projection, pool, CreateConfig());
		var candidates = new MarkerCandidateList(Array.Empty<MarkerCandidate>());

		projection.Markers = new[] { Entry("spawn:one"), Entry("spawn:two") };
		projection.LastCandidates = candidates;
		renderer.RenderForTest(currentScene: "Town");
		Assert.Equal(2, pool.ActiveCount);

		projection.Markers = new[] { Entry("spawn:one") };
		projection.LastCandidates = candidates;
		renderer.RenderForTest(currentScene: "Town");

		Assert.Equal(1, pool.ActiveCount);
	}

	private static GuideConfig CreateConfig()
	{
		var path = System.IO.Path.Combine(System.IO.Path.GetTempPath(), $"AdventureGuide.Tests.{Guid.NewGuid():N}.cfg");
		return new GuideConfig(new ConfigFile(path, saveOnInit: false));
	}

	private static MarkerEntry Entry(string positionNodeKey)
	{
		var candidate = new MarkerCandidate(
			questKey: "quest:a",
			targetNodeKey: "char:leaf",
			positionNodeKey: positionNodeKey,
			sourceNodeKey: positionNodeKey,
			scene: "Town",
			questKind: QuestMarkerKind.Objective,
			spawnCategory: SpawnCategory.Alive,
			priority: 0,
			subText: "Talk to Leaf",
			x: 1f,
			y: 2f,
			z: 3f,
			keepWhileCorpsePresent: false,
			corpseSubText: null,
			isNightSpawnNode: false,
			displayName: "Leaf",
			unlockBlockedReason: null);

		return new MarkerEntry(candidate)
		{
			Type = MarkerType.Objective,
			Priority = 0,
			SubText = "Talk to Leaf",
			Y = candidate.Y + 2.5f,
		};
	}

	private sealed class FakeMarkerProjection : IMarkerProjection
	{
		public IReadOnlyList<MarkerEntry> Markers { get; set; } = Array.Empty<MarkerEntry>();
		public MarkerCandidateList? LastCandidates { get; set; }
	}

	private sealed class FakeMarkerPool : IMarkerPool
	{
		private readonly List<FakeMarkerInstance> _instances = new();

		public int ActiveCount { get; private set; }

		public IMarkerInstance Get(int index)
		{
			while (index >= _instances.Count)
				_instances.Add(new FakeMarkerInstance());
			return _instances[index];
		}

		public void SetActiveCount(int count) => ActiveCount = count;

		public void DeactivateAll() => ActiveCount = 0;

		public void Destroy() => _instances.Clear();
	}

	private sealed class FakeMarkerInstance : IMarkerInstance
	{
		public void Configure(MarkerType type, string? subText, float markerScale, float iconSize, float subTextSize, float iconYOffset, float subTextYOffset) { }

		public void UpdateSubText(string? subText) { }

		public void SetPosition(float x, float y, float z) { }

		public void SetAlpha(float distance) { }

		public void SetActive(bool active) { }
	}
}
