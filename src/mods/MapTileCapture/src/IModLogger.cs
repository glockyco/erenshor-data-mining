namespace MapTileCapture;

/// <summary>Loader-neutral logging surface used by the capture runtime.</summary>
internal interface IModLogger
{
    void LogDebug(string message);
    void LogInfo(string message);
    void LogWarning(string message);
    void LogError(string message);
}
