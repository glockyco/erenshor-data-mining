using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class NavigationLoginTests
{
    [Fact]
    public void Menu_unbind_restores_same_slot_only_on_next_gameplay_login()
    {
        Assert.False(NavigationPolicy.ShouldLoadCharacter("Hidden", 0, 0));
        Assert.False(NavigationPolicy.ShouldLoadCharacter("Menu", -1, 0));
        Assert.False(NavigationPolicy.ShouldLoadCharacter("LoadScene", -1, 0));
        Assert.True(NavigationPolicy.ShouldLoadCharacter("Hidden", -1, 0));
        Assert.True(NavigationPolicy.ShouldLoadCharacter("Hidden", 0, 1));
        Assert.False(NavigationPolicy.ShouldLoadCharacter("Hidden", -1, null));
    }
}
