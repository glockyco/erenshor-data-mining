using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Navigation;
using AdventureGuide.Navigation.Queries;
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
	private readonly ISourceStateFactSource? _sourceState;
	private QuestResolutionQuery? _questResolutionQuery;
	private NavigableQuestsQuery? _navigableQuestsQuery;
	private NavigationTargetSnapshotsQuery? _navigationTargetSnapshotsQuery;
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
		ISourceStateFactSource? sourceState = null,
		QuestResolutionQuery? questResolutionQuery = null,
		NavigableQuestsQuery? navigableQuestsQuery = null,
		NavigationTargetSnapshotsQuery? navigationTargetSnapshotsQuery = null)
	{
		_engine = engine;
		_inventory = inventory;
		_questState = questState;
		_trackerState = trackerState;
		_navSet = navSet;
		_sourceState = sourceState;
		_questResolutionQuery = questResolutionQuery;
		_navigableQuestsQuery = navigableQuestsQuery;
		_navigationTargetSnapshotsQuery = navigationTargetSnapshotsQuery;
	}

	public Engine<FactKey> Engine => _engine;

	internal void SetQuestResolutionQuery(QuestResolutionQuery questResolutionQuery) =>
		_questResolutionQuery = questResolutionQuery;

	internal void SetNavigableQuestsQuery(NavigableQuestsQuery navigableQuestsQuery) =>
		_navigableQuestsQuery = navigableQuestsQuery;

	internal void SetNavigationTargetSnapshotsQuery(
		NavigationTargetSnapshotsQuery navigationTargetSnapshotsQuery) =>
		_navigationTargetSnapshotsQuery = navigationTargetSnapshotsQuery;

	/// <summary>Non-recording accessor for top-level callers that need the
	/// current scene string without establishing a fact dependency. Use this
	/// in <c>Plugin.Update</c> phases, <c>MarkerRenderer</c>, and
	/// <c>NavigationTargetSelector.Tick</c>. Inside a query compute, call
	/// <see cref="ReadCurrentScene"/> instead so the Scene fact is recorded.</summary>
	public string CurrentScene => RequireQuestState().CurrentScene;

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

	/// <summary>Ambient-recording accessor for the <see cref="SpawnCategory"/>
	/// of a graph node. Records each physical live source fact reported by the
	/// source state so conceptual nodes invalidate when their concrete world
	/// placements transition.
	/// Non-spawn nodes (item bag, mining, character-without-spawn, or any node
	/// outside the current scene) return <see cref="SpawnCategory.NotApplicable"/>
	/// but still record the fact, so renderers that branch on spawn state get
	/// re-evaluated when it becomes known.</summary>
	public SpawnCategory ReadSourceCategory(Node node)
	{
		if (node == null)
			throw new ArgumentNullException(nameof(node));

		var sourceState = RequireSourceState();
		foreach (var sourceKey in sourceState.GetSourceFactKeys(node))
			RequireAmbient().RecordFact(new FactKey(FactKind.SourceState, sourceKey));
		return sourceState.GetCategory(node);
	}

	/// <summary>Top-level read. Do not call from inside a query compute —
	/// use <c>ctx.Read(navigableQuestsQuery.Query, Unit.Value)</c> instead so
	/// the query-to-query dependency is recorded on the current compute.</summary>
	public NavigableQuestSet ReadNavigableQuests()
	{
		if (_navigableQuestsQuery == null)
			throw new InvalidOperationException("GuideReader not wired with NavigableQuestsQuery.");
		return _engine.Read(_navigableQuestsQuery.Query, Unit.Value);
	}

	/// <summary>Top-level read. Do not call from inside a query compute —
	/// use <c>ctx.Read(navigationTargetSnapshotsQuery.Query, scene)</c>
	/// instead so the query-to-query dependency is recorded.</summary>
	public NavigationTargetSnapshots ReadNavigationTargetSnapshots(string scene)
	{
		if (_navigationTargetSnapshotsQuery == null)
		{
			throw new InvalidOperationException(
				"GuideReader not wired with NavigationTargetSnapshotsQuery.");
		}

		using var _ = CompiledTargetsQuery.BeginSharedResolutionBatchScope();
		return _engine.Read(_navigationTargetSnapshotsQuery.Query, scene);
	}

	/// <summary>Top-level read. Do not call from inside a query compute —
	/// use <c>ctx.Read(questResolutionQuery.Query, (questKey, scene))</c>
	/// instead so the query-to-query dependency is recorded.</summary>
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
		RequireAmbient().RecordFact(new FactKey(FactKind.TrackerSet, "*"));
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
		RequireAmbient().RecordFact(new FactKey(FactKind.NavSet, "*"));
		return RequireNavSet().Keys;
	}

	private IQuestStateFactSource RequireQuestState() =>
		_questState ?? throw new InvalidOperationException("GuideReader quest state source is unavailable.");

	private ITrackerStateFactSource RequireTrackerState() =>
		_trackerState ?? throw new InvalidOperationException("GuideReader tracker state source is unavailable.");

	private INavigationSetFactSource RequireNavSet() =>
		_navSet ?? throw new InvalidOperationException("GuideReader navigation set source is unavailable.");

	private ISourceStateFactSource RequireSourceState() =>
		_sourceState ?? throw new InvalidOperationException("GuideReader source state source is unavailable.");

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

public interface ISourceStateFactSource
{
	SpawnCategory GetCategory(Node node);
	IReadOnlyCollection<string> GetSourceFactKeys(Node node);
}
