using AdventureGuide.Patches;

namespace AdventureGuide.Tests;

public sealed class QuestLogSuppressionPolicyTests
{
    [Theory]
    [InlineData(false, false, true)]
    [InlineData(false, true, true)]
    [InlineData(true, false, true)]
    [InlineData(true, true, false)]
    public void OnlyReplacementJournalKeyFramesAreSuppressed(
        bool replace,
        bool keyDown,
        bool expected
    ) => Assert.Equal(expected, QuestLogSuppressionPolicy.ShouldRunOriginal(replace, keyDown));

    [Fact]
    public void EscapeCanRunOnFrameAfterOpeningGuide()
    {
        Assert.False(QuestLogSuppressionPolicy.ShouldRunOriginal(true, true));
        Assert.True(QuestLogSuppressionPolicy.ShouldRunOriginal(true, false));
        Assert.True(QuestLogSuppressionPolicy.ShouldRunOriginal(false, true));
    }
}
