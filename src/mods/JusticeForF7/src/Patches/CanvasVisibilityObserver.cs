namespace JusticeForF7.Patches;

/// <summary>Synchronizes the game's canvas visibility with the extra world UI owned by Justice.</summary>
internal sealed class CanvasVisibilityObserver
{
    private bool? _lastCanvasEnabled;

    public void Reset() => _lastCanvasEnabled = null;

    public void Tick(WorldUIHider hider)
    {
        var canvas = GameData.MainCanvas;
        if (canvas == null)
            return;

        bool currentEnabled = canvas.enabled;
        if (_lastCanvasEnabled == null)
        {
            _lastCanvasEnabled = currentEnabled;
            return;
        }

        if (currentEnabled == _lastCanvasEnabled.Value)
        {
            hider.Tick();
            return;
        }

        _lastCanvasEnabled = currentEnabled;

        if (currentEnabled)
            hider.OnUIShown();
        else
            hider.OnUIHidden();
    }
}
