using AdventureGuide.Graph;

namespace AdventureGuide.State;

/// <summary>
/// Narrow live-state surface required by NavigationTargetSelector's per-tick
/// cache refresh path. Kept free of Unity game types so selector tests can use
/// simple fakes in the plain .NET test host.
/// </summary>
internal interface INavigationSelectorLiveState
{
	(float x, float y, float z)? GetLiveNpcPosition(Node spawnNode);
	bool IsSpawnEmpty(Node spawnNode);
	bool TryGetCachedMiningAvailability(Node miningNode, out bool available);
	bool TryGetCachedItemBagAvailability(Node itemBagNode, out bool available);
}
