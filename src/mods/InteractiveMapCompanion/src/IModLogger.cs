namespace InteractiveMapCompanion;

/// <summary>
/// Loader-neutral logging contract consumed by the shared runtime.
/// </summary>
public interface IModLogger
{
    void LogDebug(string message);
    void LogInfo(string message);
    void LogWarning(string message);
    void LogError(string message);
}
