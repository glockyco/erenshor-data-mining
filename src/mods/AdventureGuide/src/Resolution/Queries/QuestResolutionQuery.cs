using AdventureGuide.Incremental;
using AdventureGuide.State;

namespace AdventureGuide.Resolution.Queries;

public sealed class QuestResolutionQuery
{
	private readonly Query<(string QuestKey, string Scene), CompiledTargetsResult> _compiledTargets;
	private readonly Query<string, BlockingZonesResult> _blockingZones;
	private readonly Func<IReadOnlyList<ResolvedTarget>, string, QuestTargetProjector.PrecomputedBlockingZoneMap, IReadOnlyList<ResolvedQuestTarget>> _project;
	private readonly Action? _onCompute;

	public Query<(string QuestKey, string Scene), QuestResolutionRecord> Query { get; }

	public QuestResolutionQuery(
		Engine<FactKey> engine,
		CompiledTargetsQuery compiledTargets,
		BlockingZonesQuery blockingZones,
		QuestTargetProjector projector)
		: this(
			engine,
			compiledTargets.Query,
			blockingZones.Query,
			(targets, scene, blockingZoneMap) => projector.Project(targets, scene, blockingZoneMap),
			onCompute: null)
	{
	}

	internal QuestResolutionQuery(
		Engine<FactKey> engine,
		Query<(string QuestKey, string Scene), CompiledTargetsResult> compiledTargets,
		Query<string, BlockingZonesResult> blockingZones,
		Func<IReadOnlyList<ResolvedTarget>, string, QuestTargetProjector.PrecomputedBlockingZoneMap, IReadOnlyList<ResolvedQuestTarget>> project,
		Action? onCompute)
	{
		_compiledTargets = compiledTargets;
		_blockingZones = blockingZones;
		_project = project;
		_onCompute = onCompute;
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
		return new QuestResolutionRecord(
			key.QuestKey,
			key.Scene,
			compiled.Frontier,
			compiled.Targets,
			navFactory,
			blocking.ByTargetScene);
	}
}
