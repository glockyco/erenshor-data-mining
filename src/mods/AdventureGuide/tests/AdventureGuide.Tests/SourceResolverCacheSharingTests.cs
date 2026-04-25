using AdventureGuide.Graph;
using AdventureGuide.Frontier;
using AdventureGuide.Incremental;
using AdventureGuide.Resolution;
using AdventureGuide.State;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

/// <summary>
/// Verifies that UnlockRequirementCache is scoped by caller quest indices so
/// sibling callers with distinct RequiredForQuestIndex values do not share a
/// cached entry.
/// </summary>
public sealed class SourceResolverCacheSharingTests
{
	[Fact]
	public void UnlockRequirement_is_scoped_per_caller_RequiredForQuestIndex()
	{
		// Two sibling quests both accept via a giver whose unlock predicate
		// requires the same prerequisite quest to be completed. Caller-scoped
		// RequiredForQuestIndex must now produce distinct cache entries so the
		// cached targets remain a pure function of the cache key.
		var guide = new CompiledGuideBuilder()
			.AddQuest("quest:prereq", dbName: "PREREQ")
			.AddCharacter("char:gated", scene: "Forest", x: 0f, y: 0f, z: 0f)
			.AddItem("item:token")
			.AddItemSource("item:token", "char:gated")
			.AddQuest("quest:a", dbName: "QUESTA", requiredItems: new[] { ("item:token", 1) })
			.AddQuest("quest:b", dbName: "QUESTB", requiredItems: new[] { ("item:token", 1) })
			.AddUnlockPredicate("char:gated", "quest:prereq")
			.Build();

		var tracker = new QuestPhaseTracker(guide);
		tracker.Initialize(
			Array.Empty<string>(),
			new[] { "QUESTA", "QUESTB" },
			new Dictionary<string, int>(),
			Array.Empty<string>()
		);
		var evaluator = new UnlockPredicateEvaluator(guide, tracker);
		var resolver = new SourceResolver(
			guide,
			tracker,
			evaluator,
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide)
		);

		var session = new SourceResolver.ResolutionSession();

		// Resolve quest A with RequiredForQuestIndex = 100.
		var entryA = new FrontierEntry(0, QuestPhase.Accepted, 100);
		_ = resolver.ResolveTargets(entryA, "Forest", session, tracer: null);

		int cacheSizeAfterA = session.UnlockRequirementCache.Count;
		Assert.True(cacheSizeAfterA > 0, "UnlockRequirementCache must be populated by first resolution");

		// Resolve quest B with a different RequiredForQuestIndex. The cache
		// must grow because the caller-scoped key differs.
		var entryB = new FrontierEntry(1, QuestPhase.Accepted, 200);
		_ = resolver.ResolveTargets(entryB, "Forest", session, tracer: null);

		Assert.True(session.UnlockRequirementCache.Count > cacheSizeAfterA);
	}

	[Fact]
	public void CachedPrerequisiteQuestFrontier_ReplaysInventoryDependencies_OnCacheHit()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:token")
			.AddCharacter("char:source", scene: "Forest", x: 1f, y: 0f, z: 2f)
			.AddItemSource("item:token", "char:source", edgeType: (byte)EdgeType.GivesItem)
			.AddQuest("quest:prereq", dbName: "PREREQ", requiredItems: new[] { ("item:token", 1) })
			.AddQuest("quest:a", dbName: "QUESTA", givers: new[] { "quest:prereq" })
			.AddQuest("quest:b", dbName: "QUESTB", givers: new[] { "quest:prereq" })
			.Build();

		var state = new QuestStateTracker(guide);
		state.LoadState(
			currentZone: "Forest",
			activeQuests: new[] { "PREREQ" },
			completedQuests: Array.Empty<string>(),
			inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
			keyringItemKeys: Array.Empty<string>());
		var phases = new QuestPhaseTracker(guide, state);
		var resolver = new SourceResolver(
			guide,
			phases,
			new UnlockPredicateEvaluator(guide, phases),
			new StubLivePositionProvider(),
			TestPositionResolvers.Create(guide));
		var session = new SourceResolver.ResolutionSession();
		var engine = new Engine<FactKey>();
		int questBComputes = 0;

		Assert.True(guide.TryGetNodeId("quest:a", out int questANodeId));
		Assert.True(guide.TryGetNodeId("quest:b", out int questBNodeId));
		int questAIndex = guide.FindQuestIndex(questANodeId);
		int questBIndex = guide.FindQuestIndex(questBNodeId);
		var questAQuery = engine.DefineQuery<Unit, IReadOnlyList<ResolvedTarget>>(
			"QuestA",
			(_, _) => resolver.ResolveTargets(
				new FrontierEntry(questAIndex, QuestPhase.ReadyToAccept, -1),
				"Forest",
				session));
		var questBQuery = engine.DefineQuery<Unit, IReadOnlyList<ResolvedTarget>>(
			"QuestB",
			(_, _) =>
			{
				questBComputes++;
				return resolver.ResolveTargets(
					new FrontierEntry(questBIndex, QuestPhase.ReadyToAccept, -1),
					"Forest",
					session);
			});

		_ = engine.Read(questAQuery, Unit.Value);
		_ = engine.Read(questBQuery, Unit.Value);
		Assert.Equal(1, questBComputes);

		engine.InvalidateFacts(new[] { new FactKey(FactKind.InventoryItemCount, "item:token") });
		_ = engine.Read(questBQuery, Unit.Value);

		Assert.Equal(2, questBComputes);
	}
}
