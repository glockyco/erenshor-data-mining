using AdventureGuide.Graph;
using AdventureGuide.Markers;

namespace AdventureGuide.State;

/// <summary>
/// Narrow live-state surface consumed by the marker pipeline.
/// <see cref="GetMarkerLiveRenderState"/> is the per-frame projector contract;
/// the node-based methods remain available for tracker internals and focused
/// tests that exercise the underlying live-state lookups directly.
/// </summary>
internal interface IMarkerLiveStateProvider
{
	SpawnInfo GetSpawnState(Node spawnNode);
	SpawnInfo GetCharacterState(Node characterNode);
	MiningInfo GetMiningState(Node miningNode);
	NodeState GetItemBagState(Node itemBagNode);
	MarkerLiveRenderState GetMarkerLiveRenderState(MarkerCandidate candidate);
}
