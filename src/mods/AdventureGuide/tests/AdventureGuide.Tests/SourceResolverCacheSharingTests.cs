using AdventureGuide.Graph;
using AdventureGuide.Frontier;
using AdventureGuide.Resolution;
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
}
