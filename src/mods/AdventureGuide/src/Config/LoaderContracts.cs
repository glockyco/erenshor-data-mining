namespace AdventureGuide.Config;

/// <summary>Loader-neutral logging surface used by the shared Adventure Guide runtime.</summary>
public interface IModLogger
{
    void LogDebug(string message);
    void LogInfo(string message);
    void LogWarning(string message);
    void LogError(string message);
    void LogError(string message, Exception exception);
}

/// <summary>A typed, persisted configuration value independent of the host loader.</summary>
public interface IConfigValue<T> : IDisposable
{
    T Value { get; set; }
    string Key { get; }
    event EventHandler? SettingChanged;
    void SetSerializedValue(string value);
}

/// <summary>Configuration binding operations supplied by a native loader adapter.</summary>
public interface IGuideConfigBackend : IDisposable
{
    IConfigValue<T> Bind<T>(
        string section,
        string key,
        T defaultValue,
        string description,
        bool hidden = false,
        float? min = null,
        float? max = null
    );
}

internal static class AdventureGuideLog
{
    internal static IModLogger Current { get; set; } = NullModLogger.Instance;

    internal static void Reset() => Current = NullModLogger.Instance;
}

internal sealed class NullModLogger : IModLogger
{
    internal static readonly NullModLogger Instance = new();

    public void LogDebug(string message) { }

    public void LogInfo(string message) { }

    public void LogWarning(string message) { }

    public void LogError(string message) { }

    public void LogError(string message, Exception exception) { }
}
