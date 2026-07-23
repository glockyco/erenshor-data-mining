namespace AdventureGuide.Core;

/// <summary>Lifecycle phases for the shared Adventure Guide runtime.</summary>
internal enum RuntimeLifecycleState : byte
{
    Created,
    Started,
    Stopped,
}

/// <summary>Result of asking a runtime to begin startup.</summary>
internal enum RuntimeStartDecision : byte
{
    Begin,
    AlreadyStarted,
    RejectedAfterStop,
}

/// <summary>Active runtime work invoked only through the lifecycle coordinator.</summary>
internal interface IRuntimeLifecycleEffects
{
    void TickActive();

    void DrawActive();

    void StopActive();
}

/// <summary>
/// Owns runtime lifecycle transitions and dispatches frame/cleanup effects only
/// in the phases where they are valid. Both loader adapters call the public
/// runtime, which delegates every lifecycle callback through this coordinator.
/// </summary>
internal sealed class RuntimeLifecycleCoordinator
{
    private readonly IRuntimeLifecycleEffects _effects;
    private RuntimeLifecycleState _state;

    internal RuntimeLifecycleCoordinator(IRuntimeLifecycleEffects effects)
    {
        _effects = effects ?? throw new ArgumentNullException(nameof(effects));
    }

    internal RuntimeLifecycleState State => _state;

    internal RuntimeStartDecision BeginStart()
    {
        if (_state == RuntimeLifecycleState.Stopped)
            return RuntimeStartDecision.RejectedAfterStop;

        if (_state == RuntimeLifecycleState.Started)
            return RuntimeStartDecision.AlreadyStarted;

        _state = RuntimeLifecycleState.Started;
        return RuntimeStartDecision.Begin;
    }

    internal void Tick()
    {
        if (_state == RuntimeLifecycleState.Started)
            _effects.TickActive();
    }

    internal void Draw(bool visible)
    {
        if (_state == RuntimeLifecycleState.Started && visible)
            _effects.DrawActive();
    }

    internal void Stop()
    {
        if (_state == RuntimeLifecycleState.Stopped)
            return;

        _state = RuntimeLifecycleState.Stopped;
        _effects.StopActive();
    }
}
