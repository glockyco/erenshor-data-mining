using AdventureGuide.Incremental;
using AdventureGuide.Plan;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Resolution.Queries;

public sealed class CompiledTargetsQuery
{
	private readonly CompiledGuideModel _guide;
	private readonly EffectiveFrontier _frontier;
	private readonly QuestTargetResolver _resolver;
	private readonly GuideReader _reader;

	public Query<(string QuestKey, string Scene), CompiledTargetsResult> Query { get; }

	public CompiledTargetsQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		EffectiveFrontier frontier,
		QuestTargetResolver resolver,
		GuideReader reader)
	{
		_guide = guide;
		_frontier = frontier;
		_resolver = resolver;
		_reader = reader;
		Query = engine.DefineQuery<(string QuestKey, string Scene), CompiledTargetsResult>(
			name: "CompiledTargets",
			compute: Compute);
	}

	private CompiledTargetsResult Compute(
		ReadContext<FactKey> ctx,
		(string QuestKey, string Scene) key)
	{
		_reader.AttachContext(ctx);
		try
		{
			_reader.ReadQuestActive(key.QuestKey);
			_reader.ReadQuestCompleted(key.QuestKey);

			if (!_guide.TryGetNodeId(key.QuestKey, out int questNodeId))
				return CompiledTargetsResult.Empty;

			int questIndex = _guide.FindQuestIndex(questNodeId);
			if (questIndex < 0)
				return CompiledTargetsResult.Empty;

			var frontier = new List<FrontierEntry>();
			_frontier.Resolve(questIndex, frontier, -1, tracer: null);
			var targets = _resolver.Resolve(questIndex, key.Scene, frontier, session: null, tracer: null);

			return new CompiledTargetsResult(frontier.ToArray(), targets.ToArray());
		}
		finally
		{
			_reader.DetachContext();
		}
	}
}

public sealed class CompiledTargetsResult
{
	private static readonly ResolvedTargetValueComparer TargetComparer = new();

	public static CompiledTargetsResult Empty { get; } =
		new(Array.Empty<FrontierEntry>(), Array.Empty<ResolvedTarget>());

	public IReadOnlyList<FrontierEntry> Frontier { get; }
	public IReadOnlyList<ResolvedTarget> Targets { get; }

	public CompiledTargetsResult(
		IReadOnlyList<FrontierEntry> frontier,
		IReadOnlyList<ResolvedTarget> targets)
	{
		Frontier = frontier;
		Targets = targets;
	}

	public override bool Equals(object? obj) =>
		obj is CompiledTargetsResult other
		&& Frontier.SequenceEqual(other.Frontier)
		&& Targets.SequenceEqual(other.Targets, TargetComparer);

	public override int GetHashCode() => HashCode.Combine(Frontier.Count, Targets.Count);

	private sealed class ResolvedTargetValueComparer : IEqualityComparer<ResolvedTarget>
	{
		public bool Equals(ResolvedTarget x, ResolvedTarget y) =>
			x.TargetNodeId == y.TargetNodeId
			&& x.PositionNodeId == y.PositionNodeId
			&& x.Role == y.Role
			&& EqualsSemantic(x.Semantic, y.Semantic)
			&& x.X.Equals(y.X)
			&& x.Y.Equals(y.Y)
			&& x.Z.Equals(y.Z)
			&& string.Equals(x.Scene, y.Scene, StringComparison.Ordinal)
			&& x.IsLive == y.IsLive
			&& x.IsActionable == y.IsActionable
			&& x.QuestIndex == y.QuestIndex
			&& x.RequiredForQuestIndex == y.RequiredForQuestIndex
			&& x.AvailabilityPriority == y.AvailabilityPriority;

		public int GetHashCode(ResolvedTarget obj) => HashCode.Combine(
			obj.TargetNodeId,
			obj.PositionNodeId,
			obj.Role,
			obj.Scene,
			obj.IsLive,
			obj.IsActionable,
			obj.QuestIndex,
			HashCode.Combine(obj.RequiredForQuestIndex, obj.AvailabilityPriority));

		private static bool EqualsSemantic(ResolvedActionSemantic left, ResolvedActionSemantic right) =>
			left.GoalKind == right.GoalKind
			&& left.TargetKind == right.TargetKind
			&& left.ActionKind == right.ActionKind
			&& string.Equals(left.GoalNodeKey, right.GoalNodeKey, StringComparison.Ordinal)
			&& left.GoalQuantity == right.GoalQuantity
			&& string.Equals(left.KeywordText, right.KeywordText, StringComparison.Ordinal)
			&& string.Equals(left.PayloadText, right.PayloadText, StringComparison.Ordinal)
			&& string.Equals(left.TargetIdentityText, right.TargetIdentityText, StringComparison.Ordinal)
			&& string.Equals(left.ContextText, right.ContextText, StringComparison.Ordinal)
			&& string.Equals(left.RationaleText, right.RationaleText, StringComparison.Ordinal)
			&& string.Equals(left.ZoneText, right.ZoneText, StringComparison.Ordinal)
			&& string.Equals(left.AvailabilityText, right.AvailabilityText, StringComparison.Ordinal)
			&& left.PreferredMarkerKind == right.PreferredMarkerKind
			&& left.MarkerPriority == right.MarkerPriority;
	}
}
