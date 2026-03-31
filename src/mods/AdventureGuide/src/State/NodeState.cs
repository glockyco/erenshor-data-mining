namespace AdventureGuide.State;

/// <summary>
/// Sealed class hierarchy representing the live state of any graph node.
/// Subclasses carry data when the state has associated values (timers, counts, reasons).
/// Stateless states use shared singletons to avoid allocation.
/// </summary>
public abstract class NodeState
{
    // Prevent external inheritance.
    internal NodeState() { }

    /// <summary>Whether this state represents a "done" / "available" / "have it" condition.</summary>
    public virtual bool IsSatisfied => false;

    // ── Singletons for stateless states ─────────────────────────────────

    public static readonly NodeState Unknown = new UnknownState();

    // Quest
    public static readonly NodeState Completed = new QuestCompleted();
    public static readonly NodeState Active = new QuestActive();
    public static readonly NodeState NotStarted = new QuestNotStarted();
    public static readonly NodeState ImplicitlyActive = new QuestImplicitlyActive();

    // Zone line
    public static readonly NodeState Accessible = new ZoneLineAccessible();

    // Spawn
    public static readonly NodeState Alive = new SpawnAlive();
    public static readonly NodeState Disabled = new SpawnDisabled();
    public static readonly NodeState NightLocked = new SpawnNightLocked();

    // Mining
    public static readonly NodeState MineAvailable = new MiningAvailable();

    // Item bag
    public static readonly NodeState BagAvailable = new ItemBagAvailable();
    public static readonly NodeState BagGone = new ItemBagGone();

    // Door
    public static readonly NodeState Unlocked = new DoorUnlocked();
}

// ── Quest states ────────────────────────────────────────────────────────

public sealed class QuestCompleted : NodeState
{
    public override bool IsSatisfied => true;
}

public sealed class QuestActive : NodeState { }

public sealed class QuestNotStarted : NodeState { }

public sealed class QuestImplicitlyActive : NodeState { }

// ── Item state ──────────────────────────────────────────────────────────

public sealed class ItemCount : NodeState
{
    public int Count { get; }
    public ItemCount(int count) => Count = count;
    public override bool IsSatisfied => Count > 0;
}

// ── Zone line states ────────────────────────────────────────────────────

public sealed class ZoneLineAccessible : NodeState
{
    public override bool IsSatisfied => true;
}

public sealed class ZoneLineLocked : NodeState
{
    public string Reason { get; }
    public ZoneLineLocked(string reason) => Reason = reason;
}

// ── Spawn / character states ────────────────────────────────────────────

public sealed class SpawnAlive : NodeState
{
    public override bool IsSatisfied => true;
}

public sealed class SpawnDead : NodeState
{
    public float RespawnSeconds { get; }
    public SpawnDead(float respawnSeconds) => RespawnSeconds = respawnSeconds;
}

public sealed class SpawnDisabled : NodeState { }

public sealed class SpawnNightLocked : NodeState { }

public sealed class SpawnUnlockBlocked : NodeState
{
	public string Reason { get; }
	public SpawnUnlockBlocked(string reason) => Reason = reason;
}

// ── Mining node states ──────────────────────────────────────────────────

public sealed class MiningAvailable : NodeState
{
    public override bool IsSatisfied => true;
}

public sealed class MiningMined : NodeState
{
    public float RespawnSeconds { get; }
    public MiningMined(float respawnSeconds) => RespawnSeconds = respawnSeconds;
}

// ── Item bag states ─────────────────────────────────────────────────────

public sealed class ItemBagAvailable : NodeState
{
    public override bool IsSatisfied => true;
}

public sealed class ItemBagPickedUp : NodeState
{
    public float RespawnSeconds { get; }
    public ItemBagPickedUp(float respawnSeconds) => RespawnSeconds = respawnSeconds;
}

public sealed class ItemBagGone : NodeState { }

// ── Door states ─────────────────────────────────────────────────────────

public sealed class DoorUnlocked : NodeState
{
    public override bool IsSatisfied => true;
}

public sealed class DoorLocked : NodeState
{
    public string KeyItemName { get; }
    public DoorLocked(string keyItemName) => KeyItemName = keyItemName;
}

// ── Fallback ────────────────────────────────────────────────────────────

public sealed class UnknownState : NodeState { }
