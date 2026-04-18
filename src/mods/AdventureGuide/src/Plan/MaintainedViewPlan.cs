using AdventureGuide.Diagnostics;

namespace AdventureGuide.Plan;

/// <summary>
/// Unified decision record describing whether any maintained view needs a
/// refresh, and if so, whether a full rebuild is required or a specific
/// affected-key subset can be refreshed in place.
/// </summary>
internal readonly struct MaintainedViewPlan
{
	public static readonly MaintainedViewPlan None = new(
		kind: MaintainedViewRefreshKind.None,
		keys: Array.Empty<string>(),
		reason: DiagnosticTrigger.Unknown
	);

	public MaintainedViewPlan(
		MaintainedViewRefreshKind kind,
		IReadOnlyList<string> keys,
		DiagnosticTrigger reason
	)
	{
		Kind = kind;
		Keys = keys;
		Reason = reason;
	}

	public MaintainedViewRefreshKind Kind { get; }

	/// <summary>
	/// When <see cref="Kind"/> is <see cref="MaintainedViewRefreshKind.Partial"/>,
	/// contains the affected-key subset. Empty for other kinds.
	/// </summary>
	public IReadOnlyList<string> Keys { get; }

	public DiagnosticTrigger Reason { get; }

	public bool RequiresRefresh => Kind != MaintainedViewRefreshKind.None;
	public bool IsFullRebuild => Kind == MaintainedViewRefreshKind.Full;
	public bool IsPartial => Kind == MaintainedViewRefreshKind.Partial;
}

internal enum MaintainedViewRefreshKind
{
	None,
	Full,
	Partial
}
