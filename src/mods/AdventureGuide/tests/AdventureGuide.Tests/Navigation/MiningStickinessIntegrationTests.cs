using AdventureGuide.CompiledGuide;
using AdventureGuide.Frontier;
using AdventureGuide.Graph;
using AdventureGuide.Navigation;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.Position;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Navigation;

public sealed class MiningStickinessIntegrationTests
{
	private const string ZoneA = "ZoneA";
	private const float PX = 0f, PY = 0f, PZ = 0f;

	[Fact]
	public void Tick_PivotsToActionableFarTarget_AfterMiningFlipWithoutLiveWorldChanged()
	{
		var guide = new CompiledGuideBuilder()
			.AddMiningNode("mine:near", scene: ZoneA, x: 5f, y: 0f, z: 0f)
			.AddMiningNode("mine:far", scene: ZoneA, x: 50f, y: 0f, z: 0f)
			.Build();

		var near = NavigationTargetSelectorTests.MakeTarget(
			ZoneA, x: 5f, targetNodeKey: "mine:near", targetNodeType: NodeType.MiningNode);
		var far = NavigationTargetSelectorTests.MakeTarget(
			ZoneA, x: 50f, targetNodeKey: "mine:far", targetNodeType: NodeType.MiningNode);
		var targets = new[] { near, far };

		var liveState = new FakeSelectorLiveStateWithChannel();
		liveState.SetSnapshot("mine:near", LiveSourceSnapshot.MiningAvailable("mine:near", "mine:near"));
		liveState.SetSnapshot("mine:far", LiveSourceSnapshot.MiningAvailable("mine:far", "mine:far"));

		
		var snapshots = NavigationTargetSelectorTests.SnapshotSet(ZoneA, "quest:test", targets);
		var selector = NavigationTargetSelectorTests.MakeSelector(
			router: NavigationTargetSelectorTests.EmptyRouter(),
			guide: guide,
			liveState: liveState,
			clock: () => 0f,
			rerankInterval: 1f);

		selector.Tick(PX, PY, PZ, ZoneA, snapshots, liveWorldChanged: false);
		Assert.True(selector.TryGet("quest:test", out var first));
		Assert.Equal("mine:near", first.Target.TargetNodeKey);

		liveState.SetSnapshot("mine:near", LiveSourceSnapshot.Mined("mine:near", "mine:near", respawnSeconds: 30f));
		liveState.RaiseWorldChanged();

		selector.Tick(PX, PY, PZ, ZoneA, snapshots, liveWorldChanged: false);
		Assert.True(selector.TryGet("quest:test", out var second));
		Assert.Equal("mine:far", second.Target.TargetNodeKey);
		Assert.True(near.IsActionable);
	}

	private sealed class FakeSelectorLiveStateWithChannel : INavigationSelectorLiveState
	{
		private readonly Dictionary<string, LiveSourceSnapshot> _snapshots = new(StringComparer.Ordinal);

		private int _worldChangedVersion;
		private int _lastObservedVersion;

		public void RaiseWorldChanged() => _worldChangedVersion++;

		public void SetSnapshot(string targetNodeKey, LiveSourceSnapshot snapshot) =>
			_snapshots[targetNodeKey] = snapshot;

		public LiveSourceSnapshot GetLiveSourceSnapshot(string? sourceNodeKey, Node targetNode)
		{
			if (_snapshots.TryGetValue(targetNode.Key, out var snapshot))
				return snapshot;

			return LiveSourceSnapshot.Unknown(sourceNodeKey, targetNode.Key);
		}

		public bool TryConsumeLiveWorldChange()
		{
			if (_worldChangedVersion == _lastObservedVersion) return false;
			_lastObservedVersion = _worldChangedVersion;
			return true;
		}
	}
}
