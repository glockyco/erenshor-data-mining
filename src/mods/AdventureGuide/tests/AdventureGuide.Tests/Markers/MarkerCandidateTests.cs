using AdventureGuide.Markers;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using Xunit;

namespace AdventureGuide.Tests.Markers;

public sealed class MarkerCandidateTests
{
    private static MarkerCandidate Sample(
        SpawnCategory spawnCategory = SpawnCategory.Alive,
        float x = 1f,
        float y = 2f,
        float z = 3f,
        string? unlockBlockedReason = null) =>
        new MarkerCandidate(
            questKey: "quest:a",
            targetNodeKey: "char:leaf",
            positionNodeKey: "spawn:leaf-1",
            sourceNodeKey: "spawn:leaf-1",
            scene: "Town",
            questKind: QuestMarkerKind.Objective,
            spawnCategory: spawnCategory,
            priority: 0,
            subText: "Talk to Leaf",
            x: x,
            y: y,
            z: z,
            keepWhileCorpsePresent: false,
            corpseSubText: null,
            isNightSpawnNode: false,
            displayName: "Leaf",
            unlockBlockedReason: unlockBlockedReason);

    [Fact]
    public void Equals_IsTrue_ForCandidatesWithIdenticalFields()
    {
        var a = Sample();
        var b = Sample();

        Assert.Equal(a, b);
        Assert.Equal(a.GetHashCode(), b.GetHashCode());
    }

    [Fact]
    public void Equals_IsFalse_WhenSpawnCategoryDiffers()
    {
        Assert.NotEqual(Sample(), Sample(spawnCategory: SpawnCategory.Dead));
    }

    [Fact]
    public void Equals_IsFalse_WhenStaticPositionDiffers()
    {
        Assert.NotEqual(Sample(), Sample(x: 9f, y: 9f, z: 9f));
    }

    [Fact]
    public void Equals_IsFalse_WhenUnlockBlockedReasonDiffers()
    {
        Assert.NotEqual(Sample(), Sample(unlockBlockedReason: "Needs the first quest"));
    }

    [Fact]
    public void ListEquals_IsTrue_ForListsWithIdenticalSequences()
    {
        var left = new MarkerCandidateList(new[] { Sample() });
        var right = new MarkerCandidateList(new[] { Sample() });

        Assert.Equal(left, right);
    }

    [Fact]
    public void ListEquals_IsFalse_WhenSequencesDiffer()
    {
        var left = new MarkerCandidateList(new[] { Sample() });
        var right = new MarkerCandidateList(Array.Empty<MarkerCandidate>());

        Assert.NotEqual(left, right);
    }
}
