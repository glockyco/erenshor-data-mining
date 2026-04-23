using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Position;
using AdventureGuide.Position.Queries;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution.Queries;

public sealed class BlockingZonesQuery
{
	private readonly CompiledGuideModel _guide;
	private readonly ZoneRouter? _zoneRouter;
	private readonly Query<string, ZoneLineAccessibilityResult> _zoneLineAccessibility;

	public Query<string, BlockingZonesResult> Query { get; }

	public BlockingZonesQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		ZoneRouter? zoneRouter)
	{
		_guide = guide;
		_zoneRouter = zoneRouter;
		_zoneLineAccessibility = new ZoneLineAccessibilityQuery(engine, guide, zoneRouter).Query;
		Query = engine.DefineQuery<string, BlockingZonesResult>(
			name: "BlockingZones",
			compute: Compute);
	}

	private BlockingZonesResult Compute(ReadContext<FactKey> ctx, string scene)
	{
		if (_zoneRouter == null || string.IsNullOrWhiteSpace(scene))
			return BlockingZonesResult.Empty;

		foreach (var zoneLineKey in _zoneRouter.GetRouteRelevantZoneLineKeys(scene))
			ctx.Read(_zoneLineAccessibility, zoneLineKey);

		var blockedByScene = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
		foreach (var zone in _guide.NodesOfType(NodeType.Zone))
		{
			if (string.IsNullOrWhiteSpace(zone.Scene))
				continue;
			if (string.Equals(zone.Scene, scene, StringComparison.OrdinalIgnoreCase))
				continue;

			var lockedHop = _zoneRouter.FindFirstLockedHop(scene, zone.Scene);
			if (lockedHop == null)
				continue;

			if (_guide.TryGetNodeId(lockedHop.ZoneLineKey, out int zoneLineNodeId))
				blockedByScene[zone.Scene] = zoneLineNodeId;
		}

		return blockedByScene.Count == 0
			? BlockingZonesResult.Empty
			: new BlockingZonesResult(blockedByScene);
	}
}

public sealed class BlockingZonesResult
{
	public static BlockingZonesResult Empty { get; } =
		new(new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase));

	public IReadOnlyDictionary<string, int> ByTargetScene { get; }

	public BlockingZonesResult(IReadOnlyDictionary<string, int> byTargetScene) =>
		ByTargetScene = byTargetScene;

	public override bool Equals(object? obj) =>
		obj is BlockingZonesResult other
		&& ByTargetScene.Count == other.ByTargetScene.Count
		&& ByTargetScene.All(kv =>
			other.ByTargetScene.TryGetValue(kv.Key, out int value) && value == kv.Value);

	public override int GetHashCode() => ByTargetScene.Count;
}
