using AdventureGuide.Graph;
using AdventureGuide.Frontier;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Tests.Helpers;

internal sealed class QuestPhaseTrackerHarness
{
	private QuestPhaseTrackerHarness(
		CompiledGuideModel guide,
		QuestStateTracker state,
		QuestPhaseTracker phases)
	{
		Guide = guide;
		State = state;
		Phases = phases;
	}

	public CompiledGuideModel Guide { get; }
	public QuestStateTracker State { get; }
	public QuestPhaseTracker Phases { get; }

	public static QuestPhaseTrackerHarness Build()
	{
		var guide = new CompiledGuideBuilder()
			.AddItem("item:wood")
			.AddQuest("quest:fetch-water", dbName: "FetchWater", requiredItems: new[] { ("item:wood", 1) })
			.Build();
		var state = new QuestStateTracker(guide);
		state.LoadState(
			currentZone: "Forest",
			activeQuests: Array.Empty<string>(),
			completedQuests: Array.Empty<string>(),
			inventoryCounts: new Dictionary<string, int>(StringComparer.Ordinal),
			keyringItemKeys: Array.Empty<string>());
		var phases = new QuestPhaseTracker(guide, state);
		return new QuestPhaseTrackerHarness(guide, state, phases);
	}

	public int ItemIndex(string itemKey)
	{
		if (!Guide.TryGetNodeId(itemKey, out int itemNodeId))
			throw new InvalidOperationException(itemKey);

		return Guide.FindItemIndex(itemNodeId);
	}

	public int QuestIndex(string dbName)
	{
		var quest = Guide.GetQuestByDbName(dbName) ?? throw new InvalidOperationException(dbName);
		if (!Guide.TryGetNodeId(quest.Key, out int questNodeId))
			throw new InvalidOperationException(quest.Key);

		return Guide.FindQuestIndex(questNodeId);
	}
}
