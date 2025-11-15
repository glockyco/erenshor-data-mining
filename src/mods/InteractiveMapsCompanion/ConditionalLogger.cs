using BepInEx.Configuration;
using BepInEx.Logging;

public class ConditionalLogger
{
    private readonly ManualLogSource _logger;
    private readonly ConfigEntry<bool> _enableLogging;

    public ConditionalLogger(ManualLogSource logger, ConfigEntry<bool> enableLogging)
    {
        _logger = logger;
        _enableLogging = enableLogging;
    }

    public void LogInfo(string message)
    {
        if (_enableLogging.Value) _logger.LogInfo(message);
    }

    public void LogDebug(string message)
    {
        if (_enableLogging.Value) _logger.LogDebug(message);
    }

    public void LogWarning(string message)
    {
        if (_enableLogging.Value) _logger.LogWarning(message);
    }

    public void LogError(string message)
    {
        if (_enableLogging.Value) _logger.LogError(message);
    }
}