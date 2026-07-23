namespace JusticeForF7.Patches;

/// <summary>Synchronizes the game's canvas visibility with the extra world UI owned by Justice.</summary>
internal sealed class CanvasVisibilityObserver
{
    private CanvasVisibilityState _state;

    public void Reset() => _state = CanvasVisibilityPolicy.Reset();

    public void Tick(WorldUIHider hider)
    {
        var canvas = GameData.MainCanvas;
        if (canvas == null)
            return;

        var observation = CanvasVisibilityPolicy.Observe(_state, canvas.enabled);
        _state = observation.State;

        switch (observation.Action)
        {
            case CanvasVisibilityAction.None:
                break;
            case CanvasVisibilityAction.Tick:
                hider.Tick();
                break;
            case CanvasVisibilityAction.Show:
                hider.OnUIShown();
                break;
            case CanvasVisibilityAction.Hide:
                hider.OnUIHidden();
                break;
        }
    }
}
