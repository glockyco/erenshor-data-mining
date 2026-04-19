namespace AdventureGuide.Markers;

/// <summary>
/// Category derived from the SourceState fact for a source node. Describes
/// the node's availability at the moment the query ran. The renderer composes
/// this with <see cref="AdventureGuide.Resolution.QuestMarkerKind"/> and
/// per-frame live state to produce the final <see cref="MarkerType"/>.
/// </summary>
public enum SpawnCategory
{
	/// <summary>Source has no spawn semantics (item bag, mining node, character
	/// with no spawn point, or live state is unavailable). The renderer uses the
	/// QuestMarkerKind directly without applying a spawn overlay.</summary>
	NotApplicable,

	/// <summary>Live source is alive / present / available.</summary>
	Alive,

	/// <summary>Live source is dead or picked up; respawn counter applies.</summary>
	Dead,

	/// <summary>Live source is disabled and will not respawn (quest-gated
	/// despawn, infeasible quest chain, etc.). Renderer suppresses.</summary>
	Disabled,

	/// <summary>Spawn is locked by an unlock predicate (missing item, uncompleted
	/// quest prerequisite). Renderer shows a blocked marker with the reason.</summary>
	UnlockBlocked,

	/// <summary>Spawn only appears at night. Renderer shows a night marker with
	/// the current time-of-day indicator.</summary>
	NightLocked,
}
