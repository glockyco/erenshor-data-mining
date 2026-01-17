namespace InteractiveMapCompanion.State;

/// <summary>
/// Manages periodic state broadcasts to connected WebSocket clients.
/// </summary>
public interface IBroadcastLoop
{
    /// <summary>
    /// Called every frame to update timing and potentially broadcast state.
    /// </summary>
    /// <param name="deltaTime">Time elapsed since last frame in seconds.</param>
    void Tick(float deltaTime);

    /// <summary>
    /// Called when a new scene is loaded.
    /// Sends zone change notification and resets entity tracking.
    /// </summary>
    /// <param name="newZone">Name of the newly loaded scene.</param>
    void OnSceneLoaded(string newZone);
}
