using AdventureGuide.UI;

namespace AdventureGuide.Tests;

public sealed class TypingFlagSyncTests
{
    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void Active_input_reasserts_typing_every_frame(bool wasActive) =>
        Assert.True(TypingFlagSync.Next(true, wasActive, false));

    [Fact]
    public void Release_writes_false_once_and_preserves_chat()
    {
        Assert.False(TypingFlagSync.Next(false, true, false));
        Assert.Null(TypingFlagSync.Next(false, false, false));
        Assert.Null(TypingFlagSync.Next(false, true, true));
        Assert.True(TypingFlagSync.Next(true, true, true));
    }
}
