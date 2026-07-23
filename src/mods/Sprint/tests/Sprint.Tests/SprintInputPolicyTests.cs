using Sprint.Core;
using Xunit;

namespace Sprint.Tests;

public sealed class SprintInputPolicyTests
{
    [Fact]
    public void Disabled_clears_latch_and_activity_but_records_key_state()
    {
        var state = new SprintInputState(
            toggleLatched: true,
            previousKeyPressed: false,
            active: true
        );

        state = SprintInputPolicy.Advance(
            state,
            enabled: false,
            toggleMode: true,
            keyPressed: true
        );

        Assert.False(state.ToggleLatched);
        Assert.True(state.PreviousKeyPressed);
        Assert.False(state.Active);
    }

    [Fact]
    public void Reenabling_toggle_mode_while_key_is_held_does_not_retrigger()
    {
        var state = SprintInputPolicy.Advance(
            default,
            enabled: false,
            toggleMode: true,
            keyPressed: true
        );

        state = SprintInputPolicy.Advance(state, enabled: true, toggleMode: true, keyPressed: true);

        Assert.False(state.ToggleLatched);
        Assert.True(state.PreviousKeyPressed);
        Assert.False(state.Active);
    }

    [Fact]
    public void Toggle_mode_flips_only_on_rising_edges()
    {
        var state = default(SprintInputState);

        state = SprintInputPolicy.Advance(state, enabled: true, toggleMode: true, keyPressed: true);
        Assert.True(state.ToggleLatched);
        Assert.True(state.Active);

        state = SprintInputPolicy.Advance(state, enabled: true, toggleMode: true, keyPressed: true);
        Assert.True(state.ToggleLatched);
        Assert.True(state.Active);

        state = SprintInputPolicy.Advance(
            state,
            enabled: true,
            toggleMode: true,
            keyPressed: false
        );
        Assert.True(state.ToggleLatched);
        Assert.False(state.PreviousKeyPressed);
        Assert.True(state.Active);

        state = SprintInputPolicy.Advance(state, enabled: true, toggleMode: true, keyPressed: true);
        Assert.False(state.ToggleLatched);
        Assert.False(state.Active);
    }

    [Fact]
    public void Hold_mode_mirrors_key_and_preserves_latent_toggle_latch()
    {
        var state = new SprintInputState(
            toggleLatched: true,
            previousKeyPressed: false,
            active: false
        );

        state = SprintInputPolicy.Advance(
            state,
            enabled: true,
            toggleMode: false,
            keyPressed: true
        );
        Assert.True(state.ToggleLatched);
        Assert.True(state.PreviousKeyPressed);
        Assert.True(state.Active);

        state = SprintInputPolicy.Advance(
            state,
            enabled: true,
            toggleMode: false,
            keyPressed: false
        );
        Assert.True(state.ToggleLatched);
        Assert.False(state.PreviousKeyPressed);
        Assert.False(state.Active);
    }

    [Fact]
    public void Switching_from_toggle_to_hold_keeps_the_latent_latch()
    {
        var state = SprintInputPolicy.Advance(
            default,
            enabled: true,
            toggleMode: true,
            keyPressed: true
        );

        state = SprintInputPolicy.Advance(
            state,
            enabled: true,
            toggleMode: false,
            keyPressed: false
        );
        Assert.True(state.ToggleLatched);
        Assert.False(state.Active);

        state = SprintInputPolicy.Advance(
            state,
            enabled: true,
            toggleMode: false,
            keyPressed: true
        );
        Assert.True(state.ToggleLatched);
        Assert.True(state.Active);
    }

    [Fact]
    public void Switching_from_hold_to_toggle_uses_the_current_key_edge()
    {
        var state = SprintInputPolicy.Advance(
            default,
            enabled: true,
            toggleMode: false,
            keyPressed: true
        );

        state = SprintInputPolicy.Advance(state, enabled: true, toggleMode: true, keyPressed: true);
        Assert.False(state.ToggleLatched);
        Assert.False(state.Active);

        state = SprintInputPolicy.Advance(
            state,
            enabled: true,
            toggleMode: true,
            keyPressed: false
        );
        state = SprintInputPolicy.Advance(state, enabled: true, toggleMode: true, keyPressed: true);
        Assert.True(state.ToggleLatched);
        Assert.True(state.Active);
    }

    [Fact]
    public void Deactivate_preserves_latch_and_previous_key_but_clears_activity()
    {
        var state = new SprintInputState(
            toggleLatched: true,
            previousKeyPressed: true,
            active: true
        );

        state = SprintInputPolicy.Deactivate(state);

        Assert.True(state.ToggleLatched);
        Assert.True(state.PreviousKeyPressed);
        Assert.False(state.Active);
    }
}
