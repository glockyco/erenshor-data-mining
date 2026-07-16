using System.Globalization;
using AdventureGuide.Config;
using BepInEx.Configuration;
using BepInEx.Logging;

namespace AdventureGuide;

internal sealed class BepInExLogger : IModLogger
{
    private readonly ManualLogSource _log;

    internal BepInExLogger(ManualLogSource log) => _log = log;

    public void LogDebug(string message) => _log.LogDebug(message);

    public void LogInfo(string message) => _log.LogInfo(message);

    public void LogWarning(string message) => _log.LogWarning(message);

    public void LogError(string message) => _log.LogError(message);

    public void LogError(string message, Exception exception) =>
        _log.LogError($"{message}: {exception}");
}

internal sealed class BepInExConfigBackend : IGuideConfigBackend
{
    private readonly ConfigFile _config;
    private bool _disposed;

    internal BepInExConfigBackend(ConfigFile config) => _config = config;

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
        if (_disposed)
            throw new ObjectDisposedException(nameof(BepInExConfigBackend));

        AcceptableValueBase? range = CreateRange<T>(min, max);
        var tag = hidden ? new ConfigurationManagerAttributes { Browsable = false } : null;
        var entry = _config.Bind(
            section,
            key,
            defaultValue,
            new ConfigDescription(description, range, tag)
        );
        return new BepInExConfigValue<T>(entry);
    }

    public void Dispose() => _disposed = true;

    private static AcceptableValueBase? CreateRange<T>(float? min, float? max)
    {
        if (!min.HasValue || !max.HasValue)
            return null;
        if (typeof(T) == typeof(int))
            return new AcceptableValueRange<int>((int)min.Value, (int)max.Value);
        if (typeof(T) == typeof(float))
            return new AcceptableValueRange<float>(min.Value, max.Value);
        return null;
    }

    private sealed class ConfigurationManagerAttributes
    {
        public bool? Browsable { get; set; }
    }
}

internal sealed class BepInExConfigValue<T> : IConfigValue<T>
{
    private readonly ConfigEntry<T> _entry;
    private bool _disposed;

    internal BepInExConfigValue(ConfigEntry<T> entry)
    {
        _entry = entry;
        _entry.SettingChanged += OnChanged;
    }

    public T Value
    {
        get => _entry.Value;
        set => _entry.Value = value;
    }

    public string Key => $"{_entry.Definition.Section}.{_entry.Definition.Key}";

    public event EventHandler? SettingChanged;

    public void SetSerializedValue(string value) => Value = Deserialize(value);

    public void Dispose()
    {
        if (_disposed)
            return;
        _disposed = true;
        _entry.SettingChanged -= OnChanged;
        SettingChanged = null;
    }

    private void OnChanged(object sender, EventArgs args)
    {
        if (!_disposed)
            SettingChanged?.Invoke(this, args);
    }

    private static T Deserialize(string value)
    {
        if (typeof(T).IsEnum)
            return (T)Enum.Parse(typeof(T), value);
        return (T)Convert.ChangeType(value, typeof(T), CultureInfo.InvariantCulture);
    }
}
