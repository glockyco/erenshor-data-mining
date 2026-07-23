namespace JusticeForF7;

/// <summary>Loader-facing effects owned by the Justice runtime adapter.</summary>
internal interface IJusticeLifecycleEffects
{
    void Start();
    void Stop();
    void Tick();
    void SceneLoaded();
    void ReportDisabled();
}

/// <summary>
/// Owns the loader-neutral enabled/running state for the Justice adapter.
/// </summary>
internal sealed class JusticeLifecycle
{
    private readonly IJusticeLifecycleEffects _effects;
    private bool _running;
    private bool _disabledReported;

    public JusticeLifecycle(IJusticeLifecycleEffects effects)
    {
        _effects = effects;
    }

    public void Start(bool enabled)
    {
        if (_running)
            return;

        if (!enabled)
        {
            ReportDisabledOnce();
            return;
        }

        // A successful enabled start begins a new disabled-reporting cycle.
        _disabledReported = false;
        _effects.Start();
        _running = true;
    }

    public void Tick(bool enabled)
    {
        if (enabled)
        {
            Start(enabled: true);
        }
        else if (_running)
        {
            Stop();
            ReportDisabledOnce();
        }
        else
        {
            ReportDisabledOnce();
        }

        if (_running)
            _effects.Tick();
    }

    public void Stop()
    {
        if (!_running)
            return;

        try
        {
            _effects.Stop();
        }
        finally
        {
            _running = false;
        }
    }

    public void SceneLoaded()
    {
        if (_running)
            _effects.SceneLoaded();
    }

    private void ReportDisabledOnce()
    {
        if (_disabledReported)
            return;

        _disabledReported = true;
        _effects.ReportDisabled();
    }
}
