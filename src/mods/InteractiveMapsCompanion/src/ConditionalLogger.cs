using BepInEx.Configuration;
using BepInEx.Logging;

namespace InteractiveMapsCompanion;

/// <summary>
/// Wrapper for conditional logging based on configuration.
/// </summary>
internal sealed class ConditionalLogger
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
        if (_enableLogging.Value)
            _logger.LogInfo(message);
    }

    public void LogDebug(string message)
    {
        if (_enableLogging.Value)
            _logger.LogDebug(message);
    }

    public void LogError(string message)
    {
        _logger.LogError(message);
    }
}
