namespace InteractiveMapCompanion.Config;

/// <summary>
/// Configuration required by the periodic state broadcast loop.
/// </summary>
public interface IBroadcastConfig
{
    /// <summary>
    /// Interval between state broadcasts, in milliseconds.
    /// </summary>
    int UpdateInterval { get; }
}
