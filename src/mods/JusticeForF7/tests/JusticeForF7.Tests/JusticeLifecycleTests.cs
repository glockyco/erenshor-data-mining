using JusticeForF7;
using Xunit;

namespace JusticeForF7.Tests;

public sealed class JusticeLifecycleTests
{
    [Fact]
    public void Disabled_start_reports_once()
    {
        var effects = new RecordingEffects();
        var lifecycle = new JusticeLifecycle(effects);

        lifecycle.Start(enabled: false);
        lifecycle.Start(enabled: false);
        lifecycle.Tick(enabled: false);

        Assert.Equal(1, effects.DisabledReports);
        Assert.Equal(0, effects.Starts);
        Assert.Equal(0, effects.Stops);
        Assert.Equal(0, effects.Ticks);
    }

    [Fact]
    public void Start_and_tick_delegate_while_enabled()
    {
        var effects = new RecordingEffects();
        var lifecycle = new JusticeLifecycle(effects);

        lifecycle.Start(enabled: true);
        lifecycle.Tick(enabled: true);

        Assert.Equal(1, effects.Starts);
        Assert.Equal(1, effects.Ticks);
        Assert.Equal(0, effects.Stops);
    }

    [Fact]
    public void Repeated_start_is_idempotent()
    {
        var effects = new RecordingEffects();
        var lifecycle = new JusticeLifecycle(effects);

        lifecycle.Start(enabled: true);
        lifecycle.Start(enabled: true);

        Assert.Equal(1, effects.Starts);
    }

    [Fact]
    public void Live_disable_stops_reports_once_and_can_reenable()
    {
        var effects = new RecordingEffects();
        var lifecycle = new JusticeLifecycle(effects);

        lifecycle.Start(enabled: true);
        lifecycle.Tick(enabled: false);
        lifecycle.Tick(enabled: false);
        lifecycle.Tick(enabled: true);
        lifecycle.Tick(enabled: false);

        Assert.Equal(2, effects.Starts);
        Assert.Equal(2, effects.Stops);
        Assert.Equal(2, effects.DisabledReports);
        Assert.Equal(1, effects.Ticks);
    }

    [Fact]
    public void Scene_loaded_is_forwarded_only_while_running()
    {
        var effects = new RecordingEffects();
        var lifecycle = new JusticeLifecycle(effects);

        lifecycle.SceneLoaded();
        lifecycle.Start(enabled: true);
        lifecycle.SceneLoaded();
        lifecycle.Stop();
        lifecycle.SceneLoaded();

        Assert.Equal(1, effects.SceneLoads);
    }

    [Fact]
    public void Repeated_stop_runs_cleanup_once()
    {
        var effects = new RecordingEffects();
        var lifecycle = new JusticeLifecycle(effects);

        lifecycle.Start(enabled: true);
        lifecycle.Stop();
        lifecycle.Stop();

        Assert.Equal(1, effects.Stops);
    }

    [Fact]
    public void Failed_start_does_not_enter_running_state_and_can_retry()
    {
        var effects = new RecordingEffects { ThrowOnStart = true };
        var lifecycle = new JusticeLifecycle(effects);

        Assert.Throws<InvalidOperationException>(() => lifecycle.Start(enabled: true));
        Assert.Equal(1, effects.Starts);
        Assert.Equal(0, effects.Stops);

        effects.ThrowOnStart = false;
        lifecycle.Start(enabled: true);
        lifecycle.Tick(enabled: true);

        Assert.Equal(2, effects.Starts);
        Assert.Equal(1, effects.Ticks);
    }

    private sealed class RecordingEffects : IJusticeLifecycleEffects
    {
        public int Starts { get; private set; }
        public int Stops { get; private set; }
        public int Ticks { get; private set; }
        public int SceneLoads { get; private set; }
        public int DisabledReports { get; private set; }
        public bool ThrowOnStart { get; set; }

        public void Start()
        {
            Starts++;
            if (ThrowOnStart)
                throw new InvalidOperationException("startup failed");
        }

        public void Stop() => Stops++;

        public void Tick() => Ticks++;

        public void SceneLoaded() => SceneLoads++;

        public void ReportDisabled() => DisabledReports++;
    }
}
