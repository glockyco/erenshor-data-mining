using AdventureGuide.Incremental;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;

namespace AdventureGuide.State;

/// <summary>Erenshor-specific facade over <see cref="Engine{TFactKey}"/> with
/// <see cref="FactKey"/>. Typed accessors record their fact dependency on the
/// engine's ambient <see cref="ReadContext{TFactKey}"/> and forward the read to
/// the underlying tracker. Trackers also self-record on direct reads via
/// <see cref="Engine{TFactKey}.Ambient"/>, so deep code paths that bypass the
/// facade still subscribe the current compute. Each fact source is a narrow
/// interface so the facade can be unit-tested with fakes.</summary>
public sealed class GuideReader
{
	private readonly Engine<FactKey> _engine;
	private readonly IInventoryFactSource _inventory;
	private readonly IQuestStateFactSource? _questState;
	private readonly ITrackerStateFactSource? _trackerState;
	private readonly INavigationSetFactSource? _navSet;
	private QuestResolutionQuery? _questResolutionQuery;
	private IResolutionTracer? _activeTracer;

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
		INavigationSetFactSource navSet,
		QuestResolutionQuery? questResolutionQuery = null)
	{
		_engine = engine;
		_inventory = inventory;
		_questState = questState;
		_trackerState = trackerState;
		_navSet = navSet;
		_questResolutionQuery = questResolutionQuery;
	}

	public Engine<FactKey> Engine => _engine;

	internal void SetQuestResolutionQuery(QuestResolutionQuery questResolutionQuery) =>
		_questResolutionQuery = questResolutionQuery;

	public int ReadInventoryCount(string itemId)
	{
		RequireAmbient().RecordFact(new FactKey(FactKind.InventoryItemCount, itemId));
		return _inventory.GetCount(itemId);
	}

	public bool ReadQuestActive(string dbName)
	{
		RequireAmbient().RecordFact(new FactKey(FactKind.QuestActive, dbName));
		return RequireQuestState().IsActive(dbName);
	}

	public bool ReadQuestCompleted(string dbName)
	{
		RequireAmbient().RecordFact(new FactKey(FactKind.QuestCompleted, dbName));
		return RequireQuestState().IsCompleted(dbName);
	}

	public string ReadCurrentScene()
	{
		RequireAmbient().RecordFact(new FactKey(FactKind.Scene, "current"));
		return RequireQuestState().CurrentScene;
	}

	public QuestResolutionRecord ReadQuestResolution(string questKey, string scene)
	{
		if (_questResolutionQuery == null)
			throw new InvalidOperationException("GuideReader not wired with QuestResolutionQuery.");
		return _engine.Read(_questResolutionQuery.Query, (questKey, scene));
	}

	// Forces a fresh resolution bypassing any cached entry, with a tracer attached
	// for the duration of the call. Queries read ActiveTracer during compute and
	// pass it down to the resolver.
	public QuestResolutionRecord ReadQuestResolutionForTrace(
		string questKey, string scene, IResolutionTracer? tracer)
	{
		if (_questResolutionQuery == null)
			throw new InvalidOperationException("GuideReader not wired with QuestResolutionQuery.");
		_activeTracer = tracer;
		try
		{
			return _engine.ReadUncached(_questResolutionQuery.Query, (questKey, scene));
		}
		finally { _activeTracer = null; }
	}

	internal IResolutionTracer? ActiveTracer => _activeTracer;

	public IReadOnlyList<string> ReadTrackedQuests()
	{
		RequireAmbient().RecordFact(new FactKey(FactKind.QuestActive, "*"));
		return RequireTrackerState().TrackedQuests;
	}

	internal IEnumerable<string> ReadActionableQuestDbNames()
	{
		RequireAmbient().RecordFact(new FactKey(FactKind.QuestActive, "*"));
		return RequireQuestState().GetActionableQuestDbNames();
	}

	internal IEnumerable<string> ReadImplicitlyAvailableQuestDbNames()
	{
		RequireAmbient().RecordFact(new FactKey(FactKind.QuestActive, "*"));
		return RequireQuestState().GetImplicitlyAvailableQuestDbNames();
	}

	internal IReadOnlyCollection<string> ReadNavSetKeys()
	{
		RequireAmbient().RecordFact(new FactKey(FactKind.QuestActive, "*"));
		return RequireNavSet().Keys;
	}

	private IQuestStateFactSource RequireQuestState() =>
		_questState ?? throw new InvalidOperationException("GuideReader quest state source is unavailable.");

	private ITrackerStateFactSource RequireTrackerState() =>
		_trackerState ?? throw new InvalidOperationException("GuideReader tracker state source is unavailable.");

	private INavigationSetFactSource RequireNavSet() =>
		_navSet ?? throw new InvalidOperationException("GuideReader navigation set source is unavailable.");

	private static ReadContext<FactKey> RequireAmbient() =>
		Engine<FactKey>.Ambient ?? throw new InvalidOperationException(
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
