using AdventureGuide.Graph;

namespace AdventureGuide.State;

internal interface INavigationSelectorLiveState
{
	LiveSourceSnapshot GetLiveSourceSnapshot(string? sourceNodeKey, Node targetNode);
	bool TryConsumeLiveWorldChange();
}
