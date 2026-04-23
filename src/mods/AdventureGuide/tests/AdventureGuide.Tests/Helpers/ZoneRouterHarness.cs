using AdventureGuide.Graph;
using AdventureGuide.Position;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

internal sealed class ZoneRouterHarness
{
	private readonly HashSet<string> _inventory = new(StringComparer.Ordinal);

	private ZoneRouterHarness(
		CompiledGuideModel guide,
		QuestStateTracker tracker,
		UnlockEvaluator unlocks,
		ZoneRouter router)
	{
		Guide = guide;
		Tracker = tracker;
		Unlocks = unlocks;
		Router = router;
	}

	public CompiledGuideModel Guide { get; }
	public QuestStateTracker Tracker { get; }
	public UnlockEvaluator Unlocks { get; }
	public ZoneRouter Router { get; }

	public static (ZoneRouter Router, ZoneRouterHarness Harness) BuildWithZoneLineUnlockedBy(string itemKey)
	{
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "SceneA")
			.AddZone("zone:b", scene: "SceneB")
			.AddZone("zone:c", scene: "SceneC")
			.AddZoneLine("zl:ab", scene: "SceneA", destinationZoneKey: "zone:b", x: 10f, y: 0f, z: 0f)
			.AddZoneLine("zl:bc", scene: "SceneB", destinationZoneKey: "zone:c", x: 20f, y: 0f, z: 0f)
			.AddItem(itemKey)
			.AddEdge(itemKey, "zl:bc", EdgeType.UnlocksZoneLine)
			.Build();

		var tracker = CreateTracker(guide);
		var gameState = new GameState(guide);
		gameState.Register(NodeType.Quest, NodeStateResolvers.Quest(tracker));
		gameState.Register(NodeType.Item, NodeStateResolvers.Item(tracker));

		var unlocks = new UnlockEvaluator(guide, gameState, tracker);
		gameState.Register(NodeType.ZoneLine, NodeStateResolvers.ZoneLine(unlocks));

		var router = new ZoneRouter(guide, unlocks);
		var harness = new ZoneRouterHarness(guide, tracker, unlocks, router);
		return (router, harness);
	}

	public static (ZoneRouter Router, ZoneRouterHarness Harness) BuildWithZoneLineUnlockedByLiveSource(
		string characterKey,
		string runtimeSourceKey)
	{
		var guide = new CompiledGuideBuilder()
			.AddZone("zone:a", scene: "SceneA")
			.AddZone("zone:b", scene: "SceneB")
			.AddZone("zone:c", scene: "SceneC")
			.AddZoneLine("zl:ab", scene: "SceneA", destinationZoneKey: "zone:b", x: 10f, y: 0f, z: 0f)
			.AddZoneLine("zl:bc", scene: "SceneB", destinationZoneKey: "zone:c", x: 20f, y: 0f, z: 0f)
			.AddCharacter(characterKey, scene: "SceneB", x: 15f, y: 0f, z: 0f)
			.AddSpawnPoint(runtimeSourceKey, scene: "SceneB", x: 15f, y: 0f, z: 0f)
			.AddEdge(characterKey, runtimeSourceKey, EdgeType.HasSpawn)
			.AddEdge(characterKey, "zl:bc", EdgeType.UnlocksZoneLine)
			.Build();

		var tracker = CreateTracker(guide);
		var gameState = new GameState(guide);
		gameState.Register(NodeType.Quest, NodeStateResolvers.Quest(tracker));
		gameState.Register(NodeType.Item, NodeStateResolvers.Item(tracker));
		gameState.Register(
			NodeType.Character,
			node => string.Equals(node.Key, characterKey, StringComparison.Ordinal)
				? NodeState.Alive
				: NodeState.Unknown
		);

		var unlocks = new UnlockEvaluator(guide, gameState, tracker);
		gameState.Register(NodeType.ZoneLine, NodeStateResolvers.ZoneLine(unlocks));

		var router = new ZoneRouter(guide, unlocks);
		var harness = new ZoneRouterHarness(guide, tracker, unlocks, router);
		return (router, harness);
	}

	public void AddToInventory(string itemKey)
	{
		_inventory.Add(itemKey);
		Tracker.LoadState(
			currentZone: "SceneA",
			activeQuests: Array.Empty<string>(),
			completedQuests: Array.Empty<string>(),
			inventoryCounts: _inventory.ToDictionary(key => key, _ => 1, StringComparer.Ordinal),
			keyringItemKeys: Array.Empty<string>()
		);
	}

	public ChangeSet ForInventoryChange(string changedItemKey)
	{
		return new ChangeSet(
			inventoryChanged: true,
			questLogChanged: false,
			sceneChanged: false,
			liveWorldChanged: false,
			changedItemKeys: new[] { changedItemKey },
			changedQuestDbNames: Array.Empty<string>(),
			changedFacts: BuildInventoryFacts(changedItemKey)
		);
	}

	public ChangeSet ForSourceStateChange(string sourceKey)
	{
		return new ChangeSet(
			inventoryChanged: false,
			questLogChanged: false,
			sceneChanged: false,
			liveWorldChanged: true,
			changedItemKeys: Array.Empty<string>(),
			changedQuestDbNames: Array.Empty<string>(),
			changedFacts: new[]
			{
				new FactKey(FactKind.SourceState, sourceKey),
				new FactKey(FactKind.SourceState, "*")
			}
		);
	}

	public ChangeSet ForSceneChange(string sceneName)
	{
		Tracker.LoadState(
			currentZone: sceneName,
			activeQuests: Array.Empty<string>(),
			completedQuests: Array.Empty<string>(),
			inventoryCounts: _inventory.ToDictionary(key => key, _ => 1, StringComparer.Ordinal),
			keyringItemKeys: Array.Empty<string>()
		);

		return new ChangeSet(
			inventoryChanged: false,
			questLogChanged: false,
			sceneChanged: true,
			liveWorldChanged: false,
			changedItemKeys: Array.Empty<string>(),
			changedQuestDbNames: Array.Empty<string>(),
			changedFacts: new[] { new FactKey(FactKind.Scene, "current") }
		);
	}

	private static QuestStateTracker CreateTracker(CompiledGuideModel guide)
	{
		var tracker = new QuestStateTracker(guide);
		tracker.LoadState(
			currentZone: "SceneA",
			activeQuests: Array.Empty<string>(),
			completedQuests: Array.Empty<string>(),
			inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
			keyringItemKeys: Array.Empty<string>()
		);
		return tracker;
	}

	private static IReadOnlyCollection<FactKey> BuildInventoryFacts(string itemKey)
	{
		var facts = new List<FactKey> { new(FactKind.InventoryItemCount, itemKey) };
		if (string.Equals(itemKey, "item:silver-key", StringComparison.Ordinal))
			facts.Add(new FactKey(FactKind.UnlockItemPossessed, itemKey));

		return facts;
	}
}
