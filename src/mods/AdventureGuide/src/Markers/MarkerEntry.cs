
namespace AdventureGuide.Markers;

/// <summary>
/// Data for a single world marker. Produced by <see cref="MarkerComputer"/>,
/// consumed by <see cref="MarkerSystem"/> for rendering and per-frame updates.
///
/// Each entry represents one spawn point (or static position) with both
/// display state and live game object references for per-frame transitions.
/// </summary>
public sealed class MarkerEntry
{
    // ── Position (mutable — updated per-frame for live NPC tracking) ────

    public float X { get; set; }
    public float Y { get; set; }
    public float Z { get; set; }
    public string Scene { get; set; } = "";

    // ── Display (mutable — updated on alive/dead transitions) ──────────

    public MarkerType Type { get; set; }
    public int Priority { get; set; }
    public string DisplayName { get; set; } = "";
    public string SubText { get; set; } = "";

    // ── Graph context ──────────────────────────────────────────────────

    /// <summary>Spawn point node key (or other positioned node key).</summary>
    public string NodeKey { get; set; } = "";
    public string QuestKey { get; set; } = "";

    // ── Live game object references (for per-frame updates) ────────────

    /// <summary>Live SpawnPoint for per-frame alive/dead checks and timer reads.</summary>
    public SpawnPoint? LiveSpawnPoint { get; set; }

    /// <summary>Live NPC for position tracking on directly-placed NPCs (no SpawnPoint).</summary>
    public NPC? TrackedNPC { get; set; }

    /// <summary>Live MiningNode for per-frame mined/available checks and timer reads.</summary>
    public MiningNode? LiveMiningNode { get; set; }

    // ── Quest intent (for dead→alive marker restoration) ───────────────

    /// <summary>The quest-relevant marker type to restore when the NPC respawns.</summary>
    public MarkerType QuestType { get; set; }

    /// <summary>The quest-relevant priority to restore when the NPC respawns.</summary>
    public int QuestPriority { get; set; }

    /// <summary>The quest-relevant sub-text to restore when the NPC respawns.</summary>
    public string QuestSubText { get; set; } = "";

    /// <summary>Keep the quest marker on a dead corpse while it is still present and lootable.</summary>
    public bool KeepWhileCorpsePresent { get; set; }

    /// <summary>Alternate sub-text to show while a corpse remains actionable.</summary>
    public string? CorpseSubText { get; set; }

    /// <summary>True when this entry is the separate static respawn-timer marker for a spawn.</summary>
    public bool IsSpawnTimer { get; set; }
}
