using AdventureGuide.Graph;
using AdventureGuide.Frontier;
using AdventureGuide.Resolution;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests.Resolution;

public sealed class NavigableQuestResolutionsQuestIndexIntegrityTests
{
	[Fact]
	public void SharedSession_RebindsQuestIndex_PerCaller()
	{
		// Two sibling accepted quests both require the same crafted item. The shared
		// recipe subtree (item:key -> recipe:key -> item:ore -> char:wolf) populates
		// RecipeMaterialCache on the first resolve; the second resolve must still
		// emit targets tagged with its own quest index.
		var guide = new CompiledGuideBuilder()
			.AddItem("item:ore")
			.AddCharacter("char:wolf", scene: "Forest", x: 40f, y: 50f, z: 60f)
			.AddItemSource("item:ore", "char:wolf")
			.AddItem("item:key")
			.AddRecipe("recipe:key")
			.AddItemSource(
				"item:key",
				"recipe:key",
				edgeType: (byte)EdgeType.Produces,
				sourceType: (byte)NodeType.Recipe
			)
			.AddEdge("recipe:key", "item:ore", EdgeType.RequiresMaterial, quantity: 1)
			.AddEdge("recipe:key", "item:key", EdgeType.Produces)
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:key", 1) })
			.AddQuest("quest:b", dbName: "QUESTB", requiredItems: new[] { ("item:key", 1) })
			.Build();

		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA", "QUESTB" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);

		var resolver = new SourceResolver(
			guide,
			tracker,
			new UnlockPredicateEvaluator(guide, tracker),
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		Assert.True(guide.TryGetNodeId("quest:a", out int questAId));
		Assert.True(guide.TryGetNodeId("quest:b", out int questBId));
		int questAIndex = guide.FindQuestIndex(questAId);
		int questBIndex = guide.FindQuestIndex(questBId);

		var frontierA = new FrontierEntry(questAIndex, QuestPhase.Accepted, questAIndex);
		var frontierB = new FrontierEntry(questBIndex, QuestPhase.Accepted, questBIndex);
		var session = new SourceResolver.ResolutionSession();

		var targetsA = resolver.ResolveTargets(frontierA, currentScene: "Forest", session);
		var targetsB = resolver.ResolveTargets(frontierB, currentScene: "Forest", session);

		Assert.NotEmpty(targetsA);
		Assert.NotEmpty(targetsB);
		Assert.All(targetsA, target => Assert.Equal(questAIndex, target.QuestIndex));
		Assert.All(targetsB, target => Assert.Equal(questBIndex, target.QuestIndex));
	}

	private sealed class StubLivePositionProvider : ILivePositionProvider
	{
		public WorldPosition? GetLivePosition(int spawnNodeId) => null;

		public bool IsAlive(int spawnNodeId) => false;
	}
}
