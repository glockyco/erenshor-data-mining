using System.Reflection;
using AdventureGuide.Config;

namespace AdventureGuide.Tests;

public sealed class CharacterSlotStateTests
{
    [Theory]
    [InlineData("", "Returning", SlotOwnerDecision.Adopt)]
    [InlineData("Returning", "Returning", SlotOwnerDecision.Keep)]
    [InlineData("Deleted", "New", SlotOwnerDecision.Reset)]
    [InlineData("Returning", "returning", SlotOwnerDecision.Reset)]
    public void Ownership_decision_preserves_legacy_saves_and_matches_exact_names(
        string storedOwner,
        string characterName,
        SlotOwnerDecision expected
    )
    {
        Assert.Equal(expected, CharacterSlotState.DecideOwner(storedOwner, characterName));
    }

    [Fact]
    public void Registry_contains_every_declared_key_with_unique_names()
    {
        var declared = typeof(CharacterSlotState)
            .GetFields(BindingFlags.Public | BindingFlags.Static)
            .Where(field => typeof(CharacterSlotState.Key).IsAssignableFrom(field.FieldType))
            .Select(field => (CharacterSlotState.Key)field.GetValue(null)!)
            .ToArray();
        Assert.Equal(declared, CharacterSlotState.All);
        Assert.Equal(
            new[] { "Owner", "TrackedQuests", "NavQuest", "NavStep", "WorkflowRecovery" },
            CharacterSlotState.All.Select(key => key.Name)
        );
        Assert.Equal(
            CharacterSlotState.All.Count,
            CharacterSlotState.All.Select(key => key.Name).Distinct().Count()
        );
    }

    [Fact]
    public void Binding_rejects_keys_outside_the_registry()
    {
        using var config = new GuideConfig(new PersistedBackend());
        Assert.Throws<ArgumentException>(() =>
            config.BindPerCharacter(0, new CharacterSlotState.Key<string>("Unregistered", ""))
        );
    }

    [Theory]
    [InlineData("")]
    [InlineData("Returning")]
    public void Missing_or_equal_owner_preserves_all_existing_state(string owner)
    {
        var backend = SeedSlot(3, owner);
        using var config = new GuideConfig(backend);
        config.PrepareCharacter(3, "Returning");
        Assert.Equal("Returning", config.BindPerCharacter(3, CharacterSlotState.Owner).Value);
        AssertSavedState(config, 3);
    }

    [Fact]
    public void Different_owner_resets_all_entries_before_new_character_binds()
    {
        var backend = SeedSlot(3, "Deleted");
        using var config = new GuideConfig(backend);
        config.PrepareCharacter(3, "New");
        Assert.Equal("New", config.BindPerCharacter(3, CharacterSlotState.Owner).Value);
        AssertDefaultState(config, 3);
        Assert.Equal(
            CharacterSlotState.All.Count,
            backend.Values.Keys.Count(key =>
                key.StartsWith("_Character.", StringComparison.Ordinal)
            )
        );
        Assert.All(backend.CharacterBindings, binding => Assert.True(binding.Hidden));
    }

    [Fact]
    public void Reset_covers_unbound_entries_and_owner_without_touching_another_slot()
    {
        var backend = SeedSlot(3, "Deleted");
        backend.Values["_Character.TrackedQuests_Slot4"] = "other-character";
        using var config = new GuideConfig(backend);
        config.ResetCharacterSlot(3);
        Assert.Equal("", config.BindPerCharacter(3, CharacterSlotState.Owner).Value);
        AssertDefaultState(config, 3);
        Assert.Equal(
            "other-character",
            config.BindPerCharacter(4, CharacterSlotState.TrackedQuests).Value
        );
    }

    [Fact]
    public void Reset_updates_already_bound_entries_and_same_name_recreation_stays_empty()
    {
        var backend = SeedSlot(3, "Returning");
        using var config = new GuideConfig(backend);
        config.PrepareCharacter(3, "Returning");
        var tracked = config.BindPerCharacter(3, CharacterSlotState.TrackedQuests);
        var recovery = config.BindPerCharacter(3, CharacterSlotState.WorkflowRecovery);
        config.SuspendCharacter();
        config.ResetCharacterSlot(3); // EraseCharacter and successful SaveChar use this path.
        config.PrepareCharacter(3, "Returning");
        Assert.Equal("", tracked.Value);
        Assert.Equal("", recovery.Value);
        AssertDefaultState(config, 3);
        Assert.Equal("Returning", config.BindPerCharacter(3, CharacterSlotState.Owner).Value);
        Assert.Same(tracked, config.BindPerCharacter(3, CharacterSlotState.TrackedQuests));
    }

    [Fact]
    public void Zone_loads_do_not_rebind_but_logout_rechecks_ownership()
    {
        var backend = SeedSlot(3, "Returning");
        using var config = new GuideConfig(backend);
        config.PrepareCharacter(3, "Returning");
        var owner = config.BindPerCharacter(3, CharacterSlotState.Owner);
        owner.Value = "Replaced";
        config.PrepareCharacter(3, "Returning");
        AssertSavedState(config, 3);
        config.SuspendCharacter();
        config.PrepareCharacter(3, "Returning");
        AssertDefaultState(config, 3);
        Assert.Equal(1, backend.CharacterBindings.Count(binding => binding.Key == "Owner_Slot3"));
    }

    private static PersistedBackend SeedSlot(int slot, string owner)
    {
        var backend = new PersistedBackend();
        if (owner.Length > 0)
            backend.Values[$"_Character.Owner_Slot{slot}"] = owner;
        backend.Values[$"_Character.TrackedQuests_Slot{slot}"] = "quest-one;quest-two";
        backend.Values[$"_Character.NavQuest_Slot{slot}"] = "quest-one";
        backend.Values[$"_Character.NavStep_Slot{slot}"] = 2;
        backend.Values[$"_Character.WorkflowRecovery_Slot{slot}"] = "saved-recovery";
        return backend;
    }

    private static void AssertSavedState(GuideConfig config, int slot)
    {
        Assert.Equal(
            "quest-one;quest-two",
            config.BindPerCharacter(slot, CharacterSlotState.TrackedQuests).Value
        );
        Assert.Equal("quest-one", config.BindPerCharacter(slot, CharacterSlotState.NavQuest).Value);
        Assert.Equal(2, config.BindPerCharacter(slot, CharacterSlotState.NavStep).Value);
        Assert.Equal(
            "saved-recovery",
            config.BindPerCharacter(slot, CharacterSlotState.WorkflowRecovery).Value
        );
    }

    private static void AssertDefaultState(GuideConfig config, int slot)
    {
        Assert.Equal("", config.BindPerCharacter(slot, CharacterSlotState.TrackedQuests).Value);
        Assert.Equal("", config.BindPerCharacter(slot, CharacterSlotState.NavQuest).Value);
        Assert.Equal(0, config.BindPerCharacter(slot, CharacterSlotState.NavStep).Value);
        Assert.Equal("", config.BindPerCharacter(slot, CharacterSlotState.WorkflowRecovery).Value);
    }

    // Each bind returns a new wrapper, like Lunaris. GuideConfig must cache it so
    // resets update the same values that already-bound consumers read.
    private sealed class PersistedBackend : IGuideConfigBackend
    {
        public Dictionary<string, object> Values { get; } = new();
        public List<(string Key, bool Hidden)> CharacterBindings { get; } = new();

        public IConfigValue<T> Bind<T>(
            string section,
            string key,
            T defaultValue,
            string description,
            bool hidden = false,
            float? min = null,
            float? max = null
        )
        {
            if (section == "_Character")
                CharacterBindings.Add((key, hidden));
            return new PersistedValue<T>(this, $"{section}.{key}", defaultValue);
        }

        public void Dispose() { }
    }

    private sealed class PersistedValue<T> : IConfigValue<T>
    {
        private readonly PersistedBackend _backend;
        private T _value;

        public PersistedValue(PersistedBackend backend, string key, T defaultValue)
        {
            _backend = backend;
            Key = key;
            _value = backend.Values.TryGetValue(key, out var saved) ? (T)saved : defaultValue;
        }

        public string Key { get; }
        public T Value
        {
            get => _value;
            set
            {
                _value = value;
                _backend.Values[Key] = value!;
                SettingChanged?.Invoke(this, EventArgs.Empty);
            }
        }
        public event EventHandler? SettingChanged;

        public void SetSerializedValue(string value) => throw new NotSupportedException();

        public void Dispose() { }
    }
}
