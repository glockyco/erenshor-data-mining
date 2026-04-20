using AdventureGuide.Graph;
using AdventureGuide.Markers;

namespace AdventureGuide.State;

/// <summary>
/// Narrow live-state surface consumed by <see cref="MarkerProjector"/>.
/// Exists so projector-layer tests can drive projection through fakes that
/// return <see cref="SpawnInfo"/> / <see cref="MiningInfo"/> values carrying
/// null Unity refs: the projector copies those refs onto
/// <see cref="MarkerEntry"/> without dereferencing them, so the fake path
/// never invokes Unity runtime behaviour.
/// </summary>
internal interface IMarkerLiveStateProvider
{
	SpawnInfo GetSpawnState(Node spawnNode);
	SpawnInfo GetCharacterState(Node characterNode);
	MiningInfo GetMiningState(Node miningNode);
	NodeState GetItemBagState(Node itemBagNode);
}
