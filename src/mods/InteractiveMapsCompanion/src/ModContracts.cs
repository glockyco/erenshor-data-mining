namespace InteractiveMapsCompanion;

/// <summary>
/// Loader-neutral settings consumed by the legacy companion runtime.
/// </summary>
public interface IModSettings
{
    bool EnableLogging { get; }

    float SendInterval { get; }
}

/// <summary>
/// Loader-neutral logging surface consumed by the legacy companion runtime.
/// </summary>
public interface IModLogger
{
    void LogInfo(string message);

    void LogDebug(string message);

    void LogError(string message);
}
