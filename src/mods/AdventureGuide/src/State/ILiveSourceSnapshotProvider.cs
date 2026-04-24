using AdventureGuide.Graph;

namespace AdventureGuide.State;

/// <summary>
/// Narrow live-state surface consumed by resolution, navigation, and marker
/// projection without coupling the state layer to marker presentation types.
/// </summary>
internal interface ILiveSourceSnapshotProvider
{
	SpawnInfo GetSpawnState(Node spawnNode);
	SpawnInfo GetCharacterState(Node characterNode);
	MiningInfo GetMiningState(Node miningNode);
	NodeState GetItemBagState(Node itemBagNode);
	LiveSourceSnapshot GetLiveSourceSnapshot(string? sourceNodeKey, Node positionNode, Node targetNode);
}
