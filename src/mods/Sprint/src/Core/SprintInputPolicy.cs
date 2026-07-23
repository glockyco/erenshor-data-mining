namespace Sprint.Core;

/// <summary>
/// Immutable input state carried between sprint frames. The state contains no
/// loader or game references, so it can be shared by every runtime adapter.
/// </summary>
internal readonly struct SprintInputState
{
    internal bool ToggleLatched { get; }
    internal bool PreviousKeyPressed { get; }
    internal bool Active { get; }

    internal SprintInputState(bool toggleLatched, bool previousKeyPressed, bool active)
    {
        ToggleLatched = toggleLatched;
        PreviousKeyPressed = previousKeyPressed;
        Active = active;
    }
}

/// <summary>Pure, allocation-free state transitions for sprint input.</summary>
internal static class SprintInputPolicy
{
    /// <summary>
    /// Advances input by one frame while preserving the runtime's hold and
    /// toggle semantics. Disabled input clears the toggle latch and sprint
    /// activity, but still records the current key state for edge detection.
    /// </summary>
    internal static SprintInputState Advance(
        SprintInputState state,
        bool enabled,
        bool toggleMode,
        bool keyPressed
    )
    {
        if (!enabled)
            return new SprintInputState(false, keyPressed, false);

        if (toggleMode)
        {
            bool toggleLatched = state.ToggleLatched;
            if (keyPressed && !state.PreviousKeyPressed)
                toggleLatched = !toggleLatched;

            return new SprintInputState(toggleLatched, keyPressed, toggleLatched);
        }

        return new SprintInputState(state.ToggleLatched, keyPressed, keyPressed);
    }

    /// <summary>
    /// Deactivates sprint without consuming input history or the latent toggle
    /// latch, allowing a later lifecycle start to resume from the same state.
    /// </summary>
    internal static SprintInputState Deactivate(SprintInputState state) =>
        new(state.ToggleLatched, state.PreviousKeyPressed, false);
}
