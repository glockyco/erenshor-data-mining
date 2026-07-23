using Xunit;

namespace JusticeForF7.Tests;

public sealed class VisibilityPolicyTests
{
    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void First_canvas_sample_records_without_an_action(bool enabled)
    {
        var observation = CanvasVisibilityPolicy.Observe(default, enabled);

        Assert.Equal(CanvasVisibilityAction.None, observation.Action);
        Assert.True(observation.State.IsInitialized);
        Assert.Equal(enabled, observation.State.IsEnabled);
    }

    [Fact]
    public void Stable_canvas_sample_emits_tick()
    {
        var first = CanvasVisibilityPolicy.Observe(default, enabled: true);

        var stable = CanvasVisibilityPolicy.Observe(first.State, enabled: true);

        Assert.Equal(CanvasVisibilityAction.Tick, stable.Action);
    }

    [Fact]
    public void Canvas_transitions_emit_hide_then_show()
    {
        var first = CanvasVisibilityPolicy.Observe(default, enabled: true);

        var hidden = CanvasVisibilityPolicy.Observe(first.State, enabled: false);
        var shown = CanvasVisibilityPolicy.Observe(hidden.State, enabled: true);

        Assert.Equal(CanvasVisibilityAction.Hide, hidden.Action);
        Assert.Equal(CanvasVisibilityAction.Show, shown.Action);
    }

    [Fact]
    public void Reset_returns_canvas_state_to_uninitialized()
    {
        var state = CanvasVisibilityPolicy.Reset();

        Assert.False(state.IsInitialized);
        Assert.False(state.IsEnabled);
        Assert.Equal(
            CanvasVisibilityAction.None,
            CanvasVisibilityPolicy.Observe(state, enabled: false).Action
        );
    }

    [Theory]
    [InlineData((int)WorldElementKind.Nameplates)]
    [InlineData((int)WorldElementKind.DamageNumbers)]
    [InlineData((int)WorldElementKind.TargetRings)]
    [InlineData((int)WorldElementKind.XPOrbs)]
    [InlineData((int)WorldElementKind.CastBars)]
    [InlineData((int)WorldElementKind.OtherWorldText)]
    public void Hidden_enabled_category_suppresses_transient_creation(int kindValue)
    {
        var kind = (WorldElementKind)kindValue;
        var settings = new FakeSettings();

        Assert.True(VisibilityPolicy.ShouldSuppressTransient(true, settings, kind));
        Assert.False(VisibilityPolicy.ShouldSuppressTransient(false, settings, kind));

        settings.SetEnabled(kind, enabled: false);

        Assert.False(VisibilityPolicy.ShouldSuppressTransient(true, settings, kind));
    }

    [Theory]
    [InlineData((int)WorldElementKind.Nameplates)]
    [InlineData((int)WorldElementKind.DamageNumbers)]
    [InlineData((int)WorldElementKind.TargetRings)]
    [InlineData((int)WorldElementKind.XPOrbs)]
    [InlineData((int)WorldElementKind.CastBars)]
    [InlineData((int)WorldElementKind.OtherWorldText)]
    public void Hidden_disabled_category_does_not_suppress_transient_creation(int kindValue)
    {
        var kind = (WorldElementKind)kindValue;
        var settings = new FakeSettings
        {
            HideNameplates = false,
            HideDamageNumbers = false,
            HideTargetRings = false,
            HideXPOrbs = false,
            HideCastBars = false,
            HideOtherWorldText = false,
        };

        Assert.False(VisibilityPolicy.ShouldSuppressTransient(true, settings, kind));
    }

    [Fact]
    public void Unknown_world_element_kind_fails_fast()
    {
        Assert.Throws<ArgumentOutOfRangeException>(
            () => VisibilityPolicy.IsCategoryEnabled(new FakeSettings(), (WorldElementKind)99)
        );
    }

    [Theory]
    [InlineData((int)WorldElementKind.Nameplates, true)]
    [InlineData((int)WorldElementKind.DamageNumbers, true)]
    [InlineData((int)WorldElementKind.TargetRings, true)]
    [InlineData((int)WorldElementKind.XPOrbs, true)]
    [InlineData((int)WorldElementKind.CastBars, true)]
    [InlineData((int)WorldElementKind.OtherWorldText, true)]
    public void Settings_map_exactly_to_world_element_categories(int kindValue, bool expected)
    {
        var kind = (WorldElementKind)kindValue;
        var settings = new FakeSettings
        {
            HideNameplates = kind == WorldElementKind.Nameplates,
            HideDamageNumbers = kind == WorldElementKind.DamageNumbers,
            HideTargetRings = kind == WorldElementKind.TargetRings,
            HideXPOrbs = kind == WorldElementKind.XPOrbs,
            HideCastBars = kind == WorldElementKind.CastBars,
            HideOtherWorldText = kind == WorldElementKind.OtherWorldText,
        };

        Assert.Equal(expected, VisibilityPolicy.IsCategoryEnabled(settings, kind));
    }

    [Theory]
    [InlineData((int)WorldElementKind.Nameplates)]
    [InlineData((int)WorldElementKind.DamageNumbers)]
    [InlineData((int)WorldElementKind.TargetRings)]
    [InlineData((int)WorldElementKind.XPOrbs)]
    [InlineData((int)WorldElementKind.CastBars)]
    [InlineData((int)WorldElementKind.OtherWorldText)]
    public void Disabling_one_setting_disables_only_its_category(int disabledValue)
    {
        var disabled = (WorldElementKind)disabledValue;
        var settings = new FakeSettings();
        settings.SetEnabled(disabled, enabled: false);

        Assert.False(VisibilityPolicy.IsCategoryEnabled(settings, disabled));
        foreach (var kind in Enum.GetValues<WorldElementKind>())
        {
            if (kind != disabled)
                Assert.True(VisibilityPolicy.IsCategoryEnabled(settings, kind));
        }
    }

    [Fact]
    public void Disabled_or_nonpositive_rescan_interval_never_scans()
    {
        var disabled = VisibilityPolicy.AdvanceRescan(
            new RescanState(4),
            hidden: true,
            interval: 0
        );
        var negative = VisibilityPolicy.AdvanceRescan(
            new RescanState(4),
            hidden: true,
            interval: -1
        );

        Assert.False(disabled.ShouldScan);
        Assert.Equal(4, disabled.State.FramesSinceLastScan);
        Assert.False(negative.ShouldScan);
        Assert.Equal(4, negative.State.FramesSinceLastScan);
    }

    [Fact]
    public void Rescan_occurs_at_exact_threshold_and_resets_counter()
    {
        var first = VisibilityPolicy.AdvanceRescan(default, hidden: true, interval: 3);
        var second = VisibilityPolicy.AdvanceRescan(first.State, hidden: true, interval: 3);
        var threshold = VisibilityPolicy.AdvanceRescan(second.State, hidden: true, interval: 3);

        Assert.False(first.ShouldScan);
        Assert.False(second.ShouldScan);
        Assert.True(threshold.ShouldScan);
        Assert.Equal(0, threshold.State.FramesSinceLastScan);
    }

    [Fact]
    public void Rescan_reset_returns_zero_counter()
    {
        var reset = VisibilityPolicy.ResetRescan();

        Assert.Equal(0, reset.FramesSinceLastScan);
    }

    [Fact]
    public void Visible_frames_do_not_advance_rescan_counter()
    {
        var decision = VisibilityPolicy.AdvanceRescan(
            new RescanState(2),
            hidden: false,
            interval: 3
        );

        Assert.False(decision.ShouldScan);
        Assert.Equal(2, decision.State.FramesSinceLastScan);
    }

    private sealed class FakeSettings : IJusticeSettings
    {
        public bool Enabled => true;
        public bool EnableLogging => false;
        public int RescanInterval => 30;
        public bool HideNameplates { get; set; } = true;
        public bool HideDamageNumbers { get; set; } = true;
        public bool HideTargetRings { get; set; } = true;
        public bool HideXPOrbs { get; set; } = true;
        public bool HideCastBars { get; set; } = true;
        public bool HideOtherWorldText { get; set; } = true;

        public void SetEnabled(WorldElementKind kind, bool enabled)
        {
            switch (kind)
            {
                case WorldElementKind.Nameplates:
                    HideNameplates = enabled;
                    break;
                case WorldElementKind.DamageNumbers:
                    HideDamageNumbers = enabled;
                    break;
                case WorldElementKind.TargetRings:
                    HideTargetRings = enabled;
                    break;
                case WorldElementKind.XPOrbs:
                    HideXPOrbs = enabled;
                    break;
                case WorldElementKind.CastBars:
                    HideCastBars = enabled;
                    break;
                case WorldElementKind.OtherWorldText:
                    HideOtherWorldText = enabled;
                    break;
            }
        }
    }
}
