using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class QuestResolutionInvalidationTests
{
    [Fact]
    public void InventoryChange_PreservesUnrelatedQuestRecord()
    {
        var (service, harness) = ResolutionTestFactory.BuildInvalidationHarness();

        var affected = service.ResolveQuest("quest:fetch-water", harness.Scene);
        var unrelated = service.ResolveQuest("quest:slay-wolves", harness.Scene);

        harness.Emit(
            new GuideChangeSet(
                inventoryChanged: true,
                questLogChanged: false,
                sceneChanged: false,
                liveWorldChanged: false,
                changedItemKeys: new[] { "item:water-flask" },
                changedQuestDbNames: Array.Empty<string>(),
                affectedQuestKeys: new[] { "quest:fetch-water" },
                changedFacts: new[]
                {
                    new GuideFactKey(GuideFactKind.InventoryItemCount, "item:water-flask"),
                }
            )
        );

        var affectedReresolved = service.ResolveQuest("quest:fetch-water", harness.Scene);
        var unrelatedReresolved = service.ResolveQuest("quest:slay-wolves", harness.Scene);

        Assert.NotSame(affected, affectedReresolved);
        Assert.Same(unrelated, unrelatedReresolved);
    }

    [Fact]
    public void VersionBumpAlone_DoesNotClearCache()
    {
        var (service, harness) = ResolutionTestFactory.BuildInvalidationHarness();

        var before = service.ResolveQuest("quest:fetch-water", harness.Scene);
        harness.BumpVersionWithoutFacts();
        var after = service.ResolveQuest("quest:fetch-water", harness.Scene);

        Assert.Same(before, after);
    }

    [Fact]
    public void SceneChange_ClearsAllRecords()
    {
        var (service, harness) = ResolutionTestFactory.BuildInvalidationHarness();

        var before = service.ResolveQuest("quest:fetch-water", harness.Scene);

        service.InvalidateAll(
            new GuideChangeSet(
                inventoryChanged: false,
                questLogChanged: false,
                sceneChanged: true,
                liveWorldChanged: false,
                changedItemKeys: Array.Empty<string>(),
                changedQuestDbNames: Array.Empty<string>(),
                affectedQuestKeys: Array.Empty<string>(),
                changedFacts: new[] { new GuideFactKey(GuideFactKind.Scene, "current") }
            )
        );

        var after = service.ResolveQuest("quest:fetch-water", harness.Scene);

        Assert.NotSame(before, after);
    }
}
