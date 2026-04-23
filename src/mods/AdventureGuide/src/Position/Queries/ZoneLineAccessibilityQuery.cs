using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Position.Queries;

public sealed record ZoneLineAccessibilityResult(string ZoneLineKey, bool IsAccessible);

public sealed class ZoneLineAccessibilityQuery
{
	private readonly CompiledGuideModel _guide;
	private readonly ZoneRouter? _zoneRouter;

	public Query<string, ZoneLineAccessibilityResult> Query { get; }

	public ZoneLineAccessibilityQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		ZoneRouter? zoneRouter)
	{
		_guide = guide;
		_zoneRouter = zoneRouter;
		Query = engine.DefineQuery<string, ZoneLineAccessibilityResult>(
			name: "ZoneLineAccessibility",
			compute: Compute);
	}

	private ZoneLineAccessibilityResult Compute(ReadContext<FactKey> ctx, string zoneLineKey)
	{
		var node = _guide.GetNode(zoneLineKey);
		if (node == null || node.Type != NodeType.ZoneLine || !node.IsEnabled || _zoneRouter == null)
			return new ZoneLineAccessibilityResult(zoneLineKey, false);

		RecordDependencies(ctx, node);
		return new ZoneLineAccessibilityResult(zoneLineKey, _zoneRouter.IsZoneLineAccessible(zoneLineKey));
	}

	private void RecordDependencies(ReadContext<FactKey> ctx, Node zoneLine)
	{
		foreach (var edge in _guide.InEdges(zoneLine.Key, EdgeType.UnlocksZoneLine))
		{
			var source = _guide.GetNode(edge.Source);
			if (source == null)
				continue;

			switch (source.Type)
			{
				case NodeType.Item:
					ctx.RecordFact(new FactKey(FactKind.UnlockItemPossessed, source.Key));
					break;
				case NodeType.Quest when !string.IsNullOrWhiteSpace(source.DbName):
					ctx.RecordFact(new FactKey(FactKind.QuestCompleted, source.DbName!));
					break;
				default:
					ctx.RecordFact(new FactKey(FactKind.Scene, "current"));
					ctx.RecordFact(new FactKey(FactKind.SourceState, source.Key));
					break;
			}
		}
	}
}
