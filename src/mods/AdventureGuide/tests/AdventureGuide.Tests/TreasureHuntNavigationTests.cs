using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class TreasureHuntNavigationTests
{
    [Fact]
    public void Digging_returns_to_the_step_the_hunt_paused()
    {
        var hunt = new TreasureHuntNavigation();
        hunt.Pause("quest:bread", 2);

        Assert.Equal(
            TreasureHuntEndAction.RestorePaused,
            hunt.OnEnded(huntLeads: true, hasSelection: false)
        );
        Assert.True(hunt.TryTakePaused(out string questKey, out int stepOrder));
        Assert.Equal(("quest:bread", 2), (questKey, stepOrder));
        // Taken once: the next hunt starts with nothing paused.
        Assert.False(hunt.HasPaused);
    }

    [Fact]
    public void A_step_that_leads_to_the_hunt_is_followed_again_after_digging() =>
        Assert.Equal(
            TreasureHuntEndAction.ResolveSelection,
            new TreasureHuntNavigation().OnEnded(huntLeads: true, hasSelection: true)
        );

    [Fact]
    public void Digging_with_nothing_followed_before_clears_navigation() =>
        Assert.Equal(
            TreasureHuntEndAction.Clear,
            new TreasureHuntNavigation().OnEnded(huntLeads: true, hasSelection: false)
        );

    [Fact]
    public void A_choice_made_during_the_hunt_is_kept_after_digging()
    {
        var hunt = new TreasureHuntNavigation();
        hunt.Pause("quest:bread", 2);
        // Choosing other navigation drops the paused step and ends the hunt's lead.
        hunt.Drop();

        Assert.Equal(
            TreasureHuntEndAction.None,
            hunt.OnEnded(huntLeads: false, hasSelection: true)
        );
        Assert.False(hunt.HasPaused);
    }

    [Fact]
    public void The_paused_step_is_saved_while_the_hunt_leads()
    {
        var hunt = new TreasureHuntNavigation();
        hunt.Pause("quest:bread", 2);

        Assert.Equal(("quest:bread", 2), hunt.Saved(null, 0));
        hunt.Drop();
        Assert.Equal(("quest:axes", 1), hunt.Saved("quest:axes", 1));
        Assert.Equal(("", 0), hunt.Saved(null, 0));
    }

    [Fact]
    public void Without_a_selection_nothing_is_paused()
    {
        var hunt = new TreasureHuntNavigation();
        hunt.Pause(null, 0);

        Assert.False(hunt.HasPaused);
        Assert.False(hunt.TryTakePaused(out _, out _));
    }
}
