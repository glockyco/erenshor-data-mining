namespace MapTileCapture.Capture;

/// <summary>
/// Undo actions that a capture registers as it changes game state. Disposing
/// runs them in reverse order. A failing action does not stop the others: the
/// stack runs every action and then throws the failures together.
/// </summary>
public sealed class CleanupStack : IDisposable
{
    private readonly List<Action> _undo = new();

    public void Push(Action undo) => _undo.Add(undo);

    public void Dispose()
    {
        var failures = new List<Exception>();
        for (int i = _undo.Count - 1; i >= 0; i--)
        {
            try
            {
                _undo[i]();
            }
            catch (Exception ex)
            {
                failures.Add(ex);
            }
        }
        _undo.Clear();
        if (failures.Count > 0)
            throw new AggregateException(
                "Restoring the game state after a capture failed.",
                failures
            );
    }
}
