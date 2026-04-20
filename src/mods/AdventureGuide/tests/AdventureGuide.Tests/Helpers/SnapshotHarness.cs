using AdventureGuide.Diagnostics;
using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

/// <summary>
/// Wires a <see cref="CompiledGuideModel"/> + <see cref="StateSnapshot"/> (or empty state)
/// into the current game-state, unlock, and routing pipeline for tests without
/// reading live <c>GameData</c>.
/// </summary>
public sealed class SnapshotHarness
{
	public CompiledGuideModel Guide { get; }
	public GameState GameState { get; }
	public QuestStateTracker Tracker { get; }
	public UnlockEvaluator Unlocks { get; }
	public ZoneRouter Router { get; }

	private SnapshotHarness(
		CompiledGuideModel guide,
		GameState gameState,
		QuestStateTracker tracker,
		UnlockEvaluator unlocks,
		ZoneRouter router)
	{
		Guide = guide;
		GameState = gameState;
		Tracker = tracker;
		Unlocks = unlocks;
		Router = router;
	}

	public static SnapshotHarness FromSnapshot(CompiledGuideModel guide, StateSnapshot snapshot)
	{
		var tracker = new QuestStateTracker(guide);
		tracker.LoadState(
			snapshot.CurrentZone,
			snapshot.ActiveQuests,
			snapshot.CompletedQuests,
			snapshot.Inventory,
			snapshot.Keyring);

		var gameState = new GameState(guide);
		gameState.Register(NodeType.Quest, NodeStateResolvers.Quest(tracker));
		gameState.Register(NodeType.Item, NodeStateResolvers.Item(tracker));

		var liveResolver = new SnapshotLiveResolver(snapshot.LiveNodeStates);
		gameState.Register(NodeType.Character, liveResolver.Resolve);
		gameState.Register(NodeType.SpawnPoint, liveResolver.Resolve);
		gameState.Register(NodeType.MiningNode, liveResolver.Resolve);
		gameState.Register(NodeType.ItemBag, liveResolver.Resolve);
		gameState.Register(NodeType.Door, liveResolver.Resolve);

		var unlocks = new UnlockEvaluator(guide, gameState, tracker);
		gameState.Register(NodeType.ZoneLine, NodeStateResolvers.ZoneLine(unlocks));

		var router = new ZoneRouter(guide, unlocks);
		router.Rebuild();

		return new SnapshotHarness(guide, gameState, tracker, unlocks, router);
	}

	public static SnapshotHarness FromBuilder(CompiledGuideBuilder builder) =>
		FromSnapshot(builder.Build(), new StateSnapshot());
}

internal sealed class SnapshotLiveResolver
{
	private readonly Dictionary<string, LiveNodeState> _states;

	public SnapshotLiveResolver(Dictionary<string, LiveNodeState> states)
	{
		_states = states ?? new();
	}

	public NodeState Resolve(Node node)
	{
		if (!_states.TryGetValue(node.Key, out var live))
			return NodeState.Unknown;

		return live.State switch
		{
			"alive" => NodeState.Alive,
			"dead" => new SpawnDead(0f),
			"disabled" => NodeState.Disabled,
			"night_locked" => NodeState.NightLocked,
			"mine_available" => NodeState.MineAvailable,
			"bag_available" => NodeState.BagAvailable,
			"bag_gone" => NodeState.BagGone,
			"door_unlocked" => NodeState.Unlocked,
			"door_locked" => new DoorLocked("key"),
			"door_closed" => new DoorClosed(),
			_ => NodeState.Unknown,
		};
	}
}
