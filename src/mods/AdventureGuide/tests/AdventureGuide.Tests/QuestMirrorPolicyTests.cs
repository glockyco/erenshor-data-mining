using AdventureGuide.State;

namespace AdventureGuide.Tests;

public sealed class QuestMirrorPolicyTests
{
    [Theory]
    [InlineData(false, false, false)] // completed assignment or invalid quest: no addition
    [InlineData(true, true, false)] // held assignment or repeated completion
    [InlineData(true, false, false)] // removal is not an assignment/completion
    [InlineData(false, true, true)] // real addition
    public void MirrorsOnlyNewMembership(bool before, bool after, bool expected) =>
        Assert.Equal(expected, QuestMirrorPolicy.WasAdded(before, after));

    [Fact]
    public void CompletionAndNestedFollowUpAdditionAreIndependent()
    {
        // FinishQuest adds completion, then calls AssignQuest for its follow-up.
        bool parentCompletedBefore = false;
        bool followUpHeldBefore = false;
        Assert.True(QuestMirrorPolicy.WasAdded(followUpHeldBefore, true));
        Assert.True(QuestMirrorPolicy.WasAdded(parentCompletedBefore, true));
        // Repeated dialog must not re-track that now-held follow-up.
        Assert.False(QuestMirrorPolicy.WasAdded(true, true));
    }
}
