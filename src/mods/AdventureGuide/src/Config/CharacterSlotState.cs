namespace AdventureGuide.Config;

/// <summary>All persisted slot keys and defaults, shared by binding and reset.</summary>
public static class CharacterSlotState
{
    private static readonly List<Key> RegisteredKeys = new();
    public static IReadOnlyList<Key> All { get; } = RegisteredKeys.AsReadOnly();

    public static readonly Key<string> Owner = Register("Owner", "");
    public static readonly Key<string> TrackedQuests = Register("TrackedQuests", "");
    public static readonly Key<string> NavQuest = Register("NavQuest", "");
    public static readonly Key<int> NavStep = Register("NavStep", 0);
    public static readonly Key<string> WorkflowRecovery = Register("WorkflowRecovery", "");

    private static Key<T> Register<T>(string name, T defaultValue)
    {
        var key = new Key<T>(name, defaultValue);
        RegisteredKeys.Add(key);
        return key;
    }

    public abstract class Key
    {
        public string Name { get; }

        internal Key(string name) => Name = name;

        internal abstract void Reset(GuideConfig config, int slotIndex);
    }

    public sealed class Key<T> : Key
    {
        public T DefaultValue { get; }

        internal Key(string name, T defaultValue)
            : base(name) => DefaultValue = defaultValue;

        internal override void Reset(GuideConfig config, int slotIndex) =>
            config.BindPerCharacter(slotIndex, this).Value = DefaultValue;
    }

    /// <summary>Missing owners adopt existing saves without losing legacy guide state.</summary>
    public static SlotOwnerDecision DecideOwner(string storedOwner, string characterName) =>
        string.IsNullOrEmpty(storedOwner) ? SlotOwnerDecision.Adopt
        : string.Equals(storedOwner, characterName, StringComparison.Ordinal)
            ? SlotOwnerDecision.Keep
        : SlotOwnerDecision.Reset;
}

public enum SlotOwnerDecision
{
    Adopt,
    Keep,
    Reset,
}
