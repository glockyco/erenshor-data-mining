using AdventureGuide.Config;
using AdventureGuide.UI;
using UnityEngine;

namespace AdventureGuide.Tests;

public sealed class GuideConfigTests
{
    [Fact]
    public void Constructor_binds_every_setting_with_its_loader_neutral_contract()
    {
        var backend = new RecordingGuideConfigBackend();
        var config = new GuideConfig(backend);

        var expected = new[]
        {
            new ExpectedBinding(
                "General",
                "ToggleKey",
                typeof(KeyCode),
                KeyCode.L,
                false,
                null,
                null
            ),
            new ExpectedBinding(
                "General",
                "ReplaceQuestLog",
                typeof(bool),
                false,
                false,
                null,
                null
            ),
            new ExpectedBinding("General", "UiScale", typeof(float), -1f, false, -1f, 4f),
            new ExpectedBinding("General", "HistoryMaxSize", typeof(int), 100, false, 10f, 500f),
            new ExpectedBinding(
                "General",
                "ResetWindowLayout",
                typeof(bool),
                false,
                false,
                null,
                null
            ),
            new ExpectedBinding("Navigation", "ShowArrow", typeof(bool), true, false, null, null),
            new ExpectedBinding(
                "Navigation",
                "ShowGroundPath",
                typeof(bool),
                false,
                false,
                null,
                null
            ),
            new ExpectedBinding(
                "Navigation",
                "GroundPathToggleKey",
                typeof(KeyCode),
                KeyCode.P,
                false,
                null,
                null
            ),
            new ExpectedBinding("World Markers", "Enabled", typeof(bool), true, false, null, null),
            new ExpectedBinding("World Markers", "Scale", typeof(float), 1f, false, 0.05f, 2f),
            new ExpectedBinding("World Markers", "IconSize", typeof(float), 7f, false, 1f, 20f),
            new ExpectedBinding(
                "World Markers",
                "SubTextSize",
                typeof(float),
                3.5f,
                false,
                1f,
                10f
            ),
            new ExpectedBinding(
                "World Markers",
                "SubTextYOffset",
                typeof(float),
                -1f,
                false,
                -5f,
                5f
            ),
            new ExpectedBinding("World Markers", "IconYOffset", typeof(float), 1f, false, -5f, 5f),
            new ExpectedBinding("Tracker", "Enabled", typeof(bool), true, false, null, null),
            new ExpectedBinding(
                "Tracker",
                "ToggleKey",
                typeof(KeyCode),
                KeyCode.K,
                false,
                null,
                null
            ),
            new ExpectedBinding("Tracker", "AutoTrack", typeof(bool), true, false, null, null),
            new ExpectedBinding(
                "Tracker",
                "SortMode",
                typeof(string),
                "Proximity",
                false,
                null,
                null
            ),
            new ExpectedBinding("Tracker", "BackgroundOpacity", typeof(float), 0.4f, false, 0f, 1f),
            new ExpectedBinding(
                "_State",
                "FilterMode",
                typeof(QuestFilterMode),
                QuestFilterMode.Active,
                true,
                null,
                null
            ),
            new ExpectedBinding(
                "_State",
                "SortMode",
                typeof(QuestSortMode),
                QuestSortMode.ByLevel,
                true,
                null,
                null
            ),
            new ExpectedBinding("_State", "ZoneFilter", typeof(string), "", true, null, null),
        };

        Assert.Equal(expected.Length, backend.Bindings.Count);
        Assert.Equal(
            expected.Length,
            backend.Bindings.Select(binding => (binding.Section, binding.Key)).Distinct().Count()
        );

        for (var index = 0; index < expected.Length; index++)
            AssertBinding(expected[index], backend.Bindings[index]);

        var boundEntries = new object[]
        {
            config.ToggleKey,
            config.ReplaceQuestLog,
            config.UiScale,
            config.HistoryMaxSize,
            config.ResetWindowLayout,
            config.ShowArrow,
            config.ShowGroundPath,
            config.GroundPathToggleKey,
            config.ShowWorldMarkers,
            config.MarkerScale,
            config.IconSize,
            config.SubTextSize,
            config.SubTextYOffset,
            config.IconYOffset,
            config.TrackerEnabled,
            config.TrackerToggleKey,
            config.TrackerAutoTrack,
            config.TrackerSortMode,
            config.TrackerBackgroundOpacity,
            config.FilterMode,
            config.SortMode,
            config.ZoneFilter,
        };
        for (var index = 0; index < boundEntries.Length; index++)
            Assert.Same(boundEntries[index], backend.Bindings[index].Entry);

        Assert.Equal(KeyCode.L, config.ToggleKey.Value);
        Assert.Equal(KeyCode.K, config.TrackerToggleKey.Value);
        Assert.Equal(KeyCode.P, config.GroundPathToggleKey.Value);

        config.Dispose();
    }

    [Fact]
    public void BindPerCharacter_uses_hidden_slot_scoped_entries_and_preserves_defaults()
    {
        var backend = new RecordingGuideConfigBackend();
        var config = new GuideConfig(backend);

        var quest = config.BindPerCharacter(3, "SelectedQuest", "quest-key");
        var step = config.BindPerCharacter(0, "SelectedStep", 17);

        Assert.Equal("quest-key", quest.Value);
        Assert.Equal(17, step.Value);

        AssertBinding(
            new ExpectedBinding(
                "_Character",
                "SelectedQuest_Slot3",
                typeof(string),
                "quest-key",
                true,
                null,
                null
            ),
            backend.Bindings[22]
        );
        AssertBinding(
            new ExpectedBinding(
                "_Character",
                "SelectedStep_Slot0",
                typeof(int),
                17,
                true,
                null,
                null
            ),
            backend.Bindings[23]
        );

        config.Dispose();
    }

    [Fact]
    public void Dispose_releases_every_entry_and_backend_exactly_once()
    {
        var backend = new RecordingGuideConfigBackend();
        var config = new GuideConfig(backend);
        config.BindPerCharacter(2, "Recovery", "active");

        config.Dispose();

        Assert.Equal(1, backend.DisposeCount);
        Assert.All(backend.Bindings, binding => Assert.Equal(1, binding.Entry.DisposeCount));
    }

    private static void AssertBinding(ExpectedBinding expected, BindingCall actual)
    {
        Assert.Equal(expected.Section, actual.Section);
        Assert.Equal(expected.Key, actual.Key);
        Assert.Equal(expected.ValueType, actual.ValueType);
        Assert.Equal(expected.DefaultValue, actual.DefaultValue);
        Assert.Equal(expected.Hidden, actual.Hidden);
        Assert.Equal(expected.Minimum, actual.Minimum);
        Assert.Equal(expected.Maximum, actual.Maximum);
    }

    private sealed class ExpectedBinding
    {
        public ExpectedBinding(
            string section,
            string key,
            Type valueType,
            object? defaultValue,
            bool hidden,
            float? minimum,
            float? maximum
        )
        {
            Section = section;
            Key = key;
            ValueType = valueType;
            DefaultValue = defaultValue;
            Hidden = hidden;
            Minimum = minimum;
            Maximum = maximum;
        }

        public string Section { get; }
        public string Key { get; }
        public Type ValueType { get; }
        public object? DefaultValue { get; }
        public bool Hidden { get; }
        public float? Minimum { get; }
        public float? Maximum { get; }
    }

    private sealed class BindingCall
    {
        public BindingCall(
            string section,
            string key,
            Type valueType,
            object? defaultValue,
            bool hidden,
            float? minimum,
            float? maximum,
            IRecordingConfigValue entry
        )
        {
            Section = section;
            Key = key;
            ValueType = valueType;
            DefaultValue = defaultValue;
            Hidden = hidden;
            Minimum = minimum;
            Maximum = maximum;
            Entry = entry;
        }

        public string Section { get; }
        public string Key { get; }
        public Type ValueType { get; }
        public object? DefaultValue { get; }
        public bool Hidden { get; }
        public float? Minimum { get; }
        public float? Maximum { get; }
        public IRecordingConfigValue Entry { get; }
    }

    private interface IRecordingConfigValue
    {
        int DisposeCount { get; }
    }

    private sealed class RecordingGuideConfigBackend : IGuideConfigBackend
    {
        public List<BindingCall> Bindings { get; } = new();
        public int DisposeCount { get; private set; }

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
            var entry = new RecordingConfigValue<T>(key, defaultValue);
            Bindings.Add(
                new BindingCall(section, key, typeof(T), defaultValue, hidden, min, max, entry)
            );
            return entry;
        }

        public void Dispose() => DisposeCount++;
    }

    private sealed class RecordingConfigValue<T> : IConfigValue<T>, IRecordingConfigValue
    {
        private T _value;

        public RecordingConfigValue(string key, T defaultValue)
        {
            Key = key;
            _value = defaultValue;
        }

        public T Value
        {
            get => _value;
            set
            {
                _value = value;
                SettingChanged?.Invoke(this, EventArgs.Empty);
            }
        }

        public string Key { get; }
        public int DisposeCount { get; private set; }
        public event EventHandler? SettingChanged;

        public void SetSerializedValue(string value) { }

        public void Dispose() => DisposeCount++;
    }
}
