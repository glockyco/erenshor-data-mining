using System.Globalization;
using System.Reflection;
using AdventureGuide.Config;
using Lunaris;
using Lunaris.Config;

namespace AdventureGuide;

internal sealed class LunarisLogger : IModLogger
{
    private readonly ILog _log;

    internal LunarisLogger(ILog log) => _log = log;

    public void LogDebug(string message) => _log.LogDebug(message);

    public void LogInfo(string message) => _log.LogInfo(message);

    public void LogWarning(string message) => _log.LogWarning(message);

    public void LogError(string message) => _log.LogError(message);

    public void LogError(string message, Exception exception) =>
        _log.LogError($"{message}: {exception}");
}

internal sealed class LunarisConfigBackend : IGuideConfigBackend
{
    private readonly IConfig _config;
    private bool _disposed;

    internal LunarisConfigBackend(IConfig config) => _config = config;

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
            throw new ObjectDisposedException(nameof(LunarisConfigBackend));
        return new LunarisConfigValue<T>(
            _config,
            section,
            key,
            defaultValue,
            description,
            hidden,
            min,
            max
        );
    }

    public void Dispose() => _disposed = true;
}

internal sealed class LunarisConfigValue<T> : IConfigValue<T>
{
    private readonly IConfig _config;
    private readonly string _key;
    private T _value;
    private bool _disposed;

    internal LunarisConfigValue(
        IConfig config,
        string section,
        string key,
        T defaultValue,
        string description,
        bool hidden,
        float? min,
        float? max
    )
    {
        _config = config;
        _key = $"{section}.{key}";
        _value = config.Read(_key, defaultValue);
        config.SetSection(_key, section);
        config.SetDesc(_key, description);
        if (min.HasValue && max.HasValue)
            config.SetRange(_key, min.Value, max.Value);
        if (hidden)
            HideFromOptions(config, _key);
        config.OnChanged(_key, OnExternalChanged);
    }

    public T Value
    {
        get => _value;
        set
        {
            if (EqualityComparer<T>.Default.Equals(_value, value))
                return;
            _config.Write(_key, value);
        }
    }

    public string Key => _key;

    public event EventHandler? SettingChanged;

    public void SetSerializedValue(string value) => Value = Deserialize(value);

    public void Dispose()
    {
        _disposed = true;
        SettingChanged = null;
    }

    private void OnExternalChanged(object value)
    {
        if (_disposed)
            return;
        var typed = ConvertValue(value);
        if (EqualityComparer<T>.Default.Equals(_value, typed))
            return;
        _value = typed;
        SettingChanged?.Invoke(this, EventArgs.Empty);
    }

    private static T Deserialize(string value)
    {
        if (typeof(T).IsEnum)
            return (T)Enum.Parse(typeof(T), value);
        return (T)Convert.ChangeType(value, typeof(T), CultureInfo.InvariantCulture);
    }

    private static T ConvertValue(object value)
    {
        if (value is T typed)
            return typed;
        if (typeof(T).IsEnum)
        {
            if (value is string serialized)
                return (T)Enum.Parse(typeof(T), serialized);
            return (T)Enum.ToObject(typeof(T), value);
        }
        return (T)Convert.ChangeType(value, typeof(T), CultureInfo.InvariantCulture);
    }

    private static void HideFromOptions(IConfig config, string key)
    {
        config
            .GetType()
            .GetMethod("HideKey", BindingFlags.Instance | BindingFlags.NonPublic)
            ?.Invoke(config, new object[] { key });
    }
}
