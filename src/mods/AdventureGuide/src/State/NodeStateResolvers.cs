using AdventureGuide.Graph;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.State;

/// <summary>
/// Factories that produce a <see cref="System.Func{T, TResult}"/> resolving a
/// <see cref="NodeState"/> for a given <see cref="NodeType"/>. Each factory
/// captures the live trackers it needs; callers register the returned delegate
/// with <see cref="GameState.Register"/>.
/// </summary>
internal static class NodeStateResolvers
{
	public static Func<Node, NodeState> Quest(QuestStateTracker tracker) => node =>
	{
		var dbName = node.DbName;
		if (dbName == null)
			return NodeState.Unknown;
		if (tracker.IsCompleted(dbName))
			return NodeState.Completed;
		if (tracker.IsActive(dbName))
			return NodeState.Active;
		if (tracker.IsImplicitlyAvailable(dbName))
			return NodeState.ImplicitlyAvailable;
		return NodeState.NotStarted;
	};

	public static Func<Node, NodeState> Item(QuestStateTracker tracker) => node =>
		new ItemCount(tracker.CountItem(node.Key));

	public static Func<Node, NodeState> Character(LiveStateTracker live) => node =>
		live.GetCharacterState(node).State;

	public static Func<Node, NodeState> SpawnPoint(LiveStateTracker live) => node =>
		live.GetSpawnState(node).State;

	public static Func<Node, NodeState> MiningNode(LiveStateTracker live) => node =>
		live.GetMiningState(node).State;

	public static Func<Node, NodeState> ItemBag(LiveStateTracker live) => node =>
		live.GetItemBagState(node);

	public static Func<Node, NodeState> Door(
		CompiledGuideModel guide,
		QuestStateTracker tracker,
		LiveStateTracker live
	) => node => ResolveDoor(guide, tracker, live, node);

	public static Func<Node, NodeState> ZoneLine(UnlockEvaluator unlocks) => node =>
	{
		var evaluation = unlocks.Evaluate(node);
		return evaluation.IsUnlocked
			? NodeState.Accessible
			: new ZoneLineLocked(evaluation.Reason ?? "Locked");
	};

	private static NodeState ResolveDoor(
		CompiledGuideModel guide,
		QuestStateTracker tracker,
		LiveStateTracker live,
		Node node
	)
	{
		var liveDoor = live.GetDoorState(node);

		if (node.KeyItemKey == null)
			return liveDoor.FoundInScene ? liveDoor.State : NodeState.Unlocked;

		string keyName = guide.GetNode(node.KeyItemKey)?.DisplayName ?? node.KeyItemKey;

		if (liveDoor.FoundInScene)
		{
			if (liveDoor.State.IsSatisfied)
				return NodeState.Unlocked;

			return tracker.HasUnlockItem(node.KeyItemKey)
				? new DoorClosed(keyName)
				: new DoorLocked(keyName);
		}

		return tracker.HasUnlockItem(node.KeyItemKey)
			? new DoorClosed(keyName)
			: new DoorLocked(keyName);
	}
}
