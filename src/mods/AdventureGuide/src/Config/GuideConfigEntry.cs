using System.Reflection;
using Lunaris.Config;

namespace AdventureGuide.Config;

/// <summary>
/// Compatibility wrapper over Lunaris' low-level config API.
/// Keeps the BepInEx-style Value/SettingChanged shape used by the stable guide.
/// </summary>
public sealed class GuideConfigEntry<T> : IDisposable
{
    private readonly IConfig _config;
    private readonly string _key;
    private T _value;
    private bool _disposed;

    public event EventHandler? SettingChanged;

    internal GuideConfigEntry(
        IConfig config,
        string section,
        string key,
        T defaultValue,
        string description,
        bool hidden = false,
        float? min = null,
        float? max = null)
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
            if (EqualityComparer<T>.Default.Equals(_value, value)) return;
            _config.Write(_key, value);
        }
    }

    public string Key => _key;

    public void SetSerializedValue(string value)
    {
        Value = Deserialize(value);
    }

    public void Dispose()
    {
        _disposed = true;
        SettingChanged = null;
    }

    private void OnExternalChanged(object value)
    {
        if (_disposed) return;

        var typed = ConvertValue(value);
        if (EqualityComparer<T>.Default.Equals(_value, typed)) return;

        _value = typed;
        SettingChanged?.Invoke(this, EventArgs.Empty);
    }

    private static T Deserialize(string value)
    {
        var targetType = typeof(T);
        if (targetType.IsEnum)
            return (T)Enum.Parse(targetType, value);
        return (T)Convert.ChangeType(value, targetType);
    }

    private static T ConvertValue(object value)
    {
        if (value is T typed) return typed;

        var targetType = typeof(T);
        if (targetType.IsEnum)
        {
            if (value is string serialized)
                return (T)Enum.Parse(targetType, serialized);
            return (T)Enum.ToObject(targetType, value);
        }

        return (T)Convert.ChangeType(value, targetType);
    }

    private static void HideFromOptions(IConfig config, string key)
    {
        var method = config.GetType().GetMethod(
            "HideKey",
            BindingFlags.Instance | BindingFlags.NonPublic);
        method?.Invoke(config, new object[] { key });
    }
}
