using AdventureGuide.Core;

namespace AdventureGuide.Tests;

public sealed class RuntimeLifecyclePolicyTests
{
    [Fact]
    public void Active_frame_effects_run_only_between_start_and_stop()
    {
        var effects = new RecordingEffects();
        var lifecycle = new RuntimeLifecycleCoordinator(effects);

        lifecycle.Tick();
        lifecycle.Draw(visible: true);
        Assert.Equal(RuntimeLifecycleState.Created, lifecycle.State);
        Assert.Equal(0, effects.TickCount);
        Assert.Equal(0, effects.DrawCount);

        Assert.Equal(RuntimeStartDecision.Begin, lifecycle.BeginStart());
        lifecycle.Tick();
        lifecycle.Draw(visible: false);
        lifecycle.Draw(visible: true);
        Assert.Equal(1, effects.TickCount);
        Assert.Equal(1, effects.DrawCount);

        lifecycle.Stop();
        lifecycle.Tick();
        lifecycle.Draw(visible: true);
        lifecycle.Stop();
        Assert.Equal(RuntimeLifecycleState.Stopped, lifecycle.State);
        Assert.Equal(1, effects.TickCount);
        Assert.Equal(1, effects.DrawCount);
        Assert.Equal(1, effects.StopCount);
    }

    [Fact]
    public void Repeated_start_is_a_successful_no_op()
    {
        var lifecycle = new RuntimeLifecycleCoordinator(new RecordingEffects());

        Assert.Equal(RuntimeStartDecision.Begin, lifecycle.BeginStart());
        Assert.Equal(RuntimeStartDecision.AlreadyStarted, lifecycle.BeginStart());
        Assert.Equal(RuntimeLifecycleState.Started, lifecycle.State);
    }

    [Fact]
    public void Stop_before_start_is_terminal_and_runs_cleanup_once()
    {
        var effects = new RecordingEffects();
        var lifecycle = new RuntimeLifecycleCoordinator(effects);

        lifecycle.Stop();
        lifecycle.Stop();

        Assert.Equal(1, effects.StopCount);
        Assert.Equal(RuntimeStartDecision.RejectedAfterStop, lifecycle.BeginStart());
    }

    private sealed class RecordingEffects : IRuntimeLifecycleEffects
    {
        public int TickCount { get; private set; }
        public int DrawCount { get; private set; }
        public int StopCount { get; private set; }

        public void TickActive() => TickCount++;

        public void DrawActive() => DrawCount++;

        public void StopActive() => StopCount++;
    }
}

public sealed class RuntimeResourceOwnershipTests
{
    [Fact]
    public void Stop_without_a_constructed_config_disposes_backend_once()
    {
        var backend = new RecordingDisposable();
        var ownership = new RuntimeResourceOwnership(backend);

        ownership.Dispose();
        ownership.Dispose();

        Assert.Equal(1, backend.DisposeCount);
    }

    [Fact]
    public void Constructed_config_owns_backend_disposal()
    {
        var backend = new RecordingDisposable();
        var config = new OwningConfiguration(backend);
        var ownership = new RuntimeResourceOwnership(backend);
        ownership.AdoptConfiguration(config);

        ownership.Dispose();
        ownership.Dispose();

        Assert.Equal(1, config.DisposeCount);
        Assert.Equal(1, backend.DisposeCount);
    }

    [Fact]
    public void Construction_failure_before_ownership_transfer_disposes_backend()
    {
        var backend = new RecordingDisposable();
        var ownership = new RuntimeResourceOwnership(backend);

        ownership.Dispose();

        Assert.Equal(1, backend.DisposeCount);
    }

    [Fact]
    public void Startup_failure_after_config_transfer_cleans_up_through_lifecycle_once()
    {
        var backend = new RecordingDisposable();
        var config = new OwningConfiguration(backend);
        var ownership = new RuntimeResourceOwnership(backend);
        var lifecycle = new RuntimeLifecycleCoordinator(new OwnershipEffects(ownership));
        Assert.Equal(RuntimeStartDecision.Begin, lifecycle.BeginStart());
        ownership.AdoptConfiguration(config);

        lifecycle.Stop();
        lifecycle.Stop();

        Assert.Equal(1, config.DisposeCount);
        Assert.Equal(1, backend.DisposeCount);
    }

    [Fact]
    public void Construction_failure_cleanup_remains_idempotent_when_lifecycle_stops()
    {
        var backend = new RecordingDisposable();
        var ownership = new RuntimeResourceOwnership(backend);
        var lifecycle = new RuntimeLifecycleCoordinator(new OwnershipEffects(ownership));
        Assert.Equal(RuntimeStartDecision.Begin, lifecycle.BeginStart());

        ownership.Dispose();
        lifecycle.Stop();

        Assert.Equal(1, backend.DisposeCount);
    }

    [Fact]
    public void Ownership_cannot_transfer_twice_or_after_disposal()
    {
        var backend = new RecordingDisposable();
        var ownership = new RuntimeResourceOwnership(backend);
        ownership.AdoptConfiguration(new RecordingDisposable());

        Assert.Throws<InvalidOperationException>(
            () => ownership.AdoptConfiguration(new RecordingDisposable())
        );

        ownership.Dispose();
        Assert.Throws<ObjectDisposedException>(
            () => ownership.AdoptConfiguration(new RecordingDisposable())
        );
    }

    private sealed class OwnershipEffects : IRuntimeLifecycleEffects
    {
        private readonly IDisposable _ownership;

        public OwnershipEffects(IDisposable ownership)
        {
            _ownership = ownership;
        }

        public void TickActive() { }

        public void DrawActive() { }

        public void StopActive() => _ownership.Dispose();
    }

    private sealed class OwningConfiguration : IDisposable
    {
        private readonly IDisposable _backend;

        public OwningConfiguration(IDisposable backend)
        {
            _backend = backend;
        }

        public int DisposeCount { get; private set; }

        public void Dispose()
        {
            DisposeCount++;
            _backend.Dispose();
        }
    }

    private sealed class RecordingDisposable : IDisposable
    {
        public int DisposeCount { get; private set; }

        public void Dispose() => DisposeCount++;
    }
}
