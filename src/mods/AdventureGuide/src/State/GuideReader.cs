using AdventureGuide.Incremental;

namespace AdventureGuide.State;

/// <summary>Erenshor-specific wrapper over <see cref="Engine{TFactKey}"/> with
/// <see cref="FactKey"/>. Typed accessors record the appropriate fact key on
/// the active <see cref="ReadContext{TFactKey}"/> (for deps) and forward to the
/// underlying tracker (for values). Each tracker implements a narrow interface
/// so the wrapper can be unit-tested with fakes.</summary>
public sealed class GuideReader
{
	private readonly Engine<FactKey> _engine;
	private readonly IInventoryFactSource _inventory;
	private readonly IQuestStateFactSource? _questState;
	private readonly ITrackerStateFactSource? _trackerState;
	private readonly INavigationSetFactSource? _navSet;
	private ReadContext<FactKey>? _activeContext;

	public GuideReader(Engine<FactKey> engine, IInventoryFactSource inventory)
	{
		_engine = engine;
		_inventory = inventory;
	}

	public GuideReader(
		Engine<FactKey> engine,
		IInventoryFactSource inventory,
		IQuestStateFactSource questState,
		ITrackerStateFactSource trackerState,
		INavigationSetFactSource navSet)
	{
		_engine = engine;
		_inventory = inventory;
		_questState = questState;
		_trackerState = trackerState;
		_navSet = navSet;
	}

	public Engine<FactKey> Engine => _engine;

	internal void AttachContext(ReadContext<FactKey> ctx) => _activeContext = ctx;
	internal void DetachContext() => _activeContext = null;

	public int ReadInventoryCount(string itemId)
	{
		RequireContext().RecordFact(new FactKey(FactKind.InventoryItemCount, itemId));
		return _inventory.GetCount(itemId);
	}

	public bool ReadQuestActive(string dbName)
	{
		RequireContext().RecordFact(new FactKey(FactKind.QuestActive, dbName));
		return RequireQuestState().IsActive(dbName);
	}

	public bool ReadQuestCompleted(string dbName)
	{
		RequireContext().RecordFact(new FactKey(FactKind.QuestCompleted, dbName));
		return RequireQuestState().IsCompleted(dbName);
	}

	public string ReadCurrentScene()
	{
		RequireContext().RecordFact(new FactKey(FactKind.Scene, "current"));
		return RequireQuestState().CurrentScene;
	}

	// Records a coarse fact covering the whole tracked-quest list.
	public IReadOnlyList<string> ReadTrackedQuests()
	{
		RequireContext().RecordFact(new FactKey(FactKind.QuestActive, "*"));
		return RequireTrackerState().TrackedQuests;
	}

	internal IEnumerable<string> ReadActionableQuestDbNames()
	{
		RequireContext().RecordFact(new FactKey(FactKind.QuestActive, "*"));
		return RequireQuestState().GetActionableQuestDbNames();
	}

	internal IEnumerable<string> ReadImplicitlyAvailableQuestDbNames()
	{
		RequireContext().RecordFact(new FactKey(FactKind.QuestActive, "*"));
		return RequireQuestState().GetImplicitlyAvailableQuestDbNames();
	}

	internal IReadOnlyCollection<string> ReadNavSetKeys()
	{
		RequireContext().RecordFact(new FactKey(FactKind.QuestActive, "*"));
		return RequireNavSet().Keys;
	}

	private IQuestStateFactSource RequireQuestState() =>
		_questState ?? throw new InvalidOperationException("GuideReader quest state source is unavailable.");

	private ITrackerStateFactSource RequireTrackerState() =>
		_trackerState ?? throw new InvalidOperationException("GuideReader tracker state source is unavailable.");

	private INavigationSetFactSource RequireNavSet() =>
		_navSet ?? throw new InvalidOperationException("GuideReader navigation set source is unavailable.");

	private ReadContext<FactKey> RequireContext() =>
		_activeContext ?? throw new InvalidOperationException(
			"GuideReader.Read* called outside a query compute. Use engine.Read at the top level.");
}

public interface IInventoryFactSource
{
	int GetCount(string itemId);
}

public interface IQuestStateFactSource
{
	string CurrentScene { get; }
	bool IsActive(string dbName);
	bool IsCompleted(string dbName);
	IEnumerable<string> GetActionableQuestDbNames();
	IEnumerable<string> GetImplicitlyAvailableQuestDbNames();
}

public interface ITrackerStateFactSource
{
	IReadOnlyList<string> TrackedQuests { get; }
}

public interface INavigationSetFactSource
{
	IReadOnlyCollection<string> Keys { get; }
}
