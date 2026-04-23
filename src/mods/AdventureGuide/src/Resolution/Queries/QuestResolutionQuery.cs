using AdventureGuide.Frontier;
using AdventureGuide.Incremental;
using AdventureGuide.State;

namespace AdventureGuide.Resolution.Queries;

public sealed class QuestResolutionQuery
{
	private readonly Engine<FactKey> _engine;
    private readonly CompiledGuide.CompiledGuide _guide;
	private readonly QuestPhaseTracker _phases;
    private readonly Query<Unit, QuestDetailState> _detailState;
    private readonly Query<(string QuestKey, string Scene), CompiledTargetsResult> _compiledTargets;
	private readonly Query<string, BlockingZonesResult> _blockingZones;
	private readonly Func<IReadOnlyList<ResolvedTarget>, string, QuestTargetProjector.PrecomputedBlockingZoneMap, IReadOnlyList<ResolvedQuestTarget>> _project;
	private readonly Action? _onCompute;

	public Query<(string QuestKey, string Scene), QuestResolutionRecord> Query { get; }

	public QuestResolutionQuery(
		Engine<FactKey> engine,
		CompiledGuide.CompiledGuide guide,
		QuestPhaseTracker phases,
		CompiledTargetsQuery compiledTargets,
		BlockingZonesQuery blockingZones,
		QuestTargetProjector projector)
		: this(
			engine,
			guide,
			phases,
			compiledTargets.Query,
			blockingZones.Query,
			(targets, scene, blockingZoneMap) => projector.Project(targets, scene, blockingZoneMap),
			onCompute: null)
	{
	}

	internal QuestResolutionQuery(
		Engine<FactKey> engine,
		CompiledGuide.CompiledGuide guide,
		QuestPhaseTracker phases,
		Query<(string QuestKey, string Scene), CompiledTargetsResult> compiledTargets,
		Query<string, BlockingZonesResult> blockingZones,
		Func<IReadOnlyList<ResolvedTarget>, string, QuestTargetProjector.PrecomputedBlockingZoneMap, IReadOnlyList<ResolvedQuestTarget>> project,
		Action? onCompute)
	{
		_engine = engine;
        _guide = guide;
		_phases = phases;
		_compiledTargets = compiledTargets;
		_blockingZones = blockingZones;
		_project = project;
		_onCompute = onCompute;
        _detailState = engine.DefineQuery<Unit, QuestDetailState>(
            name: "QuestDetailState",
            compute: (_, _) => QuestDetailState.Capture(_guide, _phases));
        Query = engine.DefineQuery<(string, string), QuestResolutionRecord>(
			name: "QuestResolution",
			compute: Compute);
	}

	private QuestResolutionRecord Compute(
		ReadContext<FactKey> ctx,
		(string QuestKey, string Scene) key)
	{
		_onCompute?.Invoke();
		var compiled = ctx.Read(_compiledTargets, key);
		var blocking = ctx.Read(_blockingZones, key.Scene);
		var blockingZoneMap = new QuestTargetProjector.PrecomputedBlockingZoneMap(
			key.Scene,
			blocking.ByTargetScene);
		Func<IReadOnlyList<ResolvedQuestTarget>> navFactory =
            () => _project(compiled.Targets, key.Scene, blockingZoneMap);
        Func<QuestDetailState> detailStateFactory = () => _engine.Read(_detailState, Unit.Value);
		return new QuestResolutionRecord(
			key.QuestKey,
			key.Scene,
			compiled.Frontier,
			compiled.Targets,
			navFactory,
			blocking.ByTargetScene,
            detailStateFactory);
	}
}
