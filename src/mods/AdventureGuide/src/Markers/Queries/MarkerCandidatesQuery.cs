using AdventureGuide.Graph;
using AdventureGuide.Incremental;
using AdventureGuide.Navigation.Queries;
using AdventureGuide.Resolution;
using AdventureGuide.Resolution.Queries;
using AdventureGuide.State;
using CompiledGuideModel = AdventureGuide.CompiledGuide.CompiledGuide;

namespace AdventureGuide.Markers.Queries;

/// <summary>
/// Engine-mediated projection that, for a given scene, produces the ordered
/// list of <see cref="MarkerCandidate"/> values covering every quest-relevant
/// world marker the projector must display. Static inputs (compiled blueprints,
/// resolved targets, spawn category) are baked into the candidate;
/// per-frame overlays (respawn timers, night-hour clock, live NPC tracking)
/// are applied by the projector without invalidating this cache.
/// </summary>
public sealed class MarkerCandidatesQuery
{
	private readonly CompiledGuideModel _guide;
	private readonly GuideReader _reader;
	private readonly Query<Unit, NavigableQuestSet> _navigableQuests;
	private readonly Query<(string QuestKey, string Scene), QuestResolutionRecord> _questResolution;

	public Query<string, MarkerCandidateList> Query { get; }

	public MarkerCandidatesQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		GuideReader reader,
		NavigableQuestsQuery navigableQuests,
		QuestResolutionQuery questResolution)
		: this(engine, guide, reader, navigableQuests.Query, questResolution.Query)
	{
	}

	internal MarkerCandidatesQuery(
		Engine<FactKey> engine,
		CompiledGuideModel guide,
		GuideReader reader,
		Query<Unit, NavigableQuestSet> navigableQuests,
		Query<(string QuestKey, string Scene), QuestResolutionRecord> questResolution)
	{
		_guide = guide;
		_reader = reader;
		_navigableQuests = navigableQuests;
		_questResolution = questResolution;
		Query = engine.DefineQuery<string, MarkerCandidateList>(
			name: "MarkerCandidates",
			compute: Compute);
	}

	private MarkerCandidateList Compute(ReadContext<FactKey> ctx, string scene)
	{
		// Sub-query dep: navigable quests. The engine records a query-to-query
		// dep here so invalidations to NavSet/TrackerSet/QuestActive propagate.
		var navigable = ctx.Read(_navigableQuests, Unit.Value);

		// Wildcard set reads record their own facts via GuideReader.
		var navSetKeys = new HashSet<string>(_reader.ReadNavSetKeys(), StringComparer.Ordinal);
		var trackedDbNames = new HashSet<string>(
			_reader.ReadTrackedQuests(),
			StringComparer.OrdinalIgnoreCase);
		var actionableDbNames = new HashSet<string>(
			_reader.ReadActionableQuestDbNames(),
			StringComparer.OrdinalIgnoreCase);
		var implicitDbNames = new HashSet<string>(
			_reader.ReadImplicitlyAvailableQuestDbNames(),
			StringComparer.OrdinalIgnoreCase);

		// Union: explicit navigable keys + every scene-local giver/completion
		// blueprint. Scene-local blueprints are static guide data, not fact-driven.
		var questKeys = new HashSet<string>(navigable.Keys, StringComparer.Ordinal);
		foreach (var bp in _guide.GetQuestGiversInScene(scene))
			questKeys.Add(bp.QuestKey);
		foreach (var bp in _guide.GetQuestCompletionsInScene(scene))
			questKeys.Add(bp.QuestKey);

		var candidates = new List<MarkerCandidate>();
		foreach (var questKey in questKeys.OrderBy(k => k, StringComparer.Ordinal))
		{
			var quest = _guide.GetNode(questKey);
			if (quest == null || quest.Type != NodeType.Quest || string.IsNullOrEmpty(quest.DbName))
				continue;

			bool explicitlySelected =
				navSetKeys.Contains(quest.Key) || trackedDbNames.Contains(quest.DbName!);
			bool isActive = actionableDbNames.Contains(quest.DbName!);

			if (explicitlySelected || isActive)
			{
				var resolution = ctx.Read(_questResolution, (quest.Key, scene));
				EmitActiveCandidates(quest, resolution, scene, candidates);
				continue;
			}

			if (implicitDbNames.Contains(quest.DbName!))
			{
				EmitImplicitCompletionCandidates(quest, scene, candidates);
				continue;
			}

			// Quest-giver path: visible while the quest is not yet completed
			// (or is repeatable). Record per-quest completion fact so the
			// candidate invalidates when the player finishes the quest.
			bool completed = _reader.ReadQuestCompleted(quest.DbName!);
			if (!completed || quest.Repeatable)
				EmitQuestGiverCandidates(quest, scene, candidates);
		}

		SuppressBlockedAtOccupiedPositions(candidates);
		return new MarkerCandidateList(candidates.AsReadOnly());
	}

	private void EmitActiveCandidates(
		Node quest,
		QuestResolutionRecord resolution,
		string scene,
		List<MarkerCandidate> sink)
	{
		for (int i = 0; i < resolution.CompiledTargets.Count; i++)
		{
			var target = resolution.CompiledTargets[i];
			if (!MatchesScene(target.Scene, scene))
				continue;

			var targetNode = _guide.GetNode(_guide.GetNodeKey(target.TargetNodeId));
			var positionNode = _guide.GetNode(_guide.GetNodeKey(target.PositionNodeId));
			if (targetNode == null || positionNode == null)
				continue;

			var category = ReadSpawnCategoryForPosition(positionNode, targetNode);
			if (category == SpawnCategory.Disabled)
				continue;

			var instruction = MarkerTextBuilder.BuildInstruction(target.Semantic);
			// Current live snapshots own dead/corpse presentation. The candidate
			// remains the actionable quest marker only; respawn/dead lifecycle is
			// projected later from the current source snapshot.
			string? corpseSubText = null;
			bool keepWhileCorpse = false;

			var (x, y, z) = ResolveStaticPosition(positionNode, target.X, target.Y, target.Z);
			string displayName = targetNode.DisplayName;
			string? blockedReason = ExtractBlockedReason(category, target.Semantic);

			sink.Add(new MarkerCandidate(
				questKey: quest.Key,
				targetNodeKey: targetNode.Key,
				positionNodeKey: positionNode.Key,
				sourceNodeKey: positionNode.Key,
				scene: positionNode.Scene ?? targetNode.Scene ?? scene,
				questKind: instruction.Kind,
				spawnCategory: category,
				priority: instruction.Priority,
				subText: instruction.SubText,
				x: x,
				y: y,
				z: z,
				keepWhileCorpsePresent: keepWhileCorpse,
				corpseSubText: corpseSubText,
				isNightSpawnNode: positionNode.NightSpawn,
				displayName: displayName,
				unlockBlockedReason: blockedReason));
		}
	}

	private void EmitImplicitCompletionCandidates(
		Node quest,
		string scene,
		List<MarkerCandidate> sink)
	{
		bool ready = IsImplicitCompletionReady(quest);
		foreach (var blueprint in _guide.GetQuestCompletionsInScene(scene))
		{
			if (blueprint.QuestKey != quest.Key)
				continue;

			var targetNode = _guide.GetNode(blueprint.TargetNodeKey);
			var positionNode = _guide.GetNode(blueprint.PositionNodeKey);
			if (targetNode == null || positionNode == null)
				continue;

			var semantic = ResolvedActionSemanticBuilder.BuildQuestCompletion(
				_guide, quest, targetNode, blueprint, ready);
			var instruction = MarkerTextBuilder.BuildInstruction(semantic);

			var category = ReadSpawnCategoryForPosition(positionNode, targetNode);
			if (category == SpawnCategory.Disabled)
				continue;

			var (x, y, z) = ResolveStaticPosition(positionNode, null, null, null);

			sink.Add(new MarkerCandidate(questKey: quest.Key, targetNodeKey: targetNode.Key, positionNodeKey: positionNode.Key, sourceNodeKey: positionNode.Key, scene: positionNode.Scene ?? scene, questKind: instruction.Kind, spawnCategory: category, priority: instruction.Priority, subText: instruction.SubText, x: x, y: y, z: z, keepWhileCorpsePresent: false, corpseSubText: null, isNightSpawnNode: positionNode.NightSpawn, displayName: targetNode.DisplayName, unlockBlockedReason: ExtractBlockedReason(category, semantic)));
		}
	}

	private void EmitQuestGiverCandidates(
		Node quest,
		string scene,
		List<MarkerCandidate> sink)
	{
		foreach (var blueprint in _guide.GetQuestGiversInScene(scene))
		{
			if (blueprint.QuestKey != quest.Key)
				continue;

			var characterNode = _guide.GetNode(blueprint.CharacterKey);
			var positionNode = _guide.GetNode(blueprint.PositionNodeKey);
			if (characterNode == null || positionNode == null)
				continue;

			string? blockedRequirement = FindFirstMissingRequirement(blueprint.RequiredQuestDbNames);
			var semantic = ResolvedActionSemanticBuilder.BuildQuestGiver(
				_guide, quest, characterNode, blueprint, blockedRequirement);
			var instruction = MarkerTextBuilder.BuildInstruction(semantic);

			var category = ReadSpawnCategoryForPosition(positionNode, characterNode);
			if (category == SpawnCategory.Disabled)
				continue;

			var (x, y, z) = ResolveStaticPosition(positionNode, null, null, null);

			sink.Add(new MarkerCandidate(questKey: quest.Key, targetNodeKey: characterNode.Key, positionNodeKey: positionNode.Key, sourceNodeKey: positionNode.Key, scene: positionNode.Scene ?? characterNode.Scene ?? scene, questKind: instruction.Kind, spawnCategory: category, priority: instruction.Priority, subText: instruction.SubText, x: x, y: y, z: z, keepWhileCorpsePresent: false, corpseSubText: null, isNightSpawnNode: positionNode.NightSpawn, displayName: characterNode.DisplayName, unlockBlockedReason: ExtractBlockedReason(category, semantic)));
		}
	}

	private string? FindFirstMissingRequirement(IReadOnlyList<string> requiredQuestDbNames)
	{
		for (int i = 0; i < requiredQuestDbNames.Count; i++)
		{
			var dbName = requiredQuestDbNames[i];
			if (_reader.ReadQuestCompleted(dbName))
				continue;
			var quest = _guide.GetQuestByDbName(dbName);
			return quest?.DisplayName ?? dbName;
		}
		return null;
	}

	private bool IsImplicitCompletionReady(Node quest)
	{
		var required = _guide.OutEdges(quest.Key, EdgeType.RequiresItem);
		for (int i = 0; i < required.Count; i++)
		{
			int qty = required[i].Quantity ?? 1;
			if (_reader.ReadInventoryCount(required[i].Target) < qty)
				return false;
		}
		return true;
	}

	private SpawnCategory ReadSpawnCategoryForPosition(Node positionNode, Node? targetNode)
	{
		// Ambient-record and return the category of the position where the
		// marker will render. For characters whose spawn has no directly-placed
		// node, the position is the character node itself; pass that through.
		if (positionNode.Type == NodeType.SpawnPoint
			|| positionNode.Type == NodeType.Character
			|| positionNode.IsDirectlyPlaced)
		{
			return _reader.ReadSourceCategory(positionNode);
		}

		if (targetNode != null && targetNode.Type == NodeType.Character)
			return _reader.ReadSourceCategory(targetNode);

		return SpawnCategory.NotApplicable;
	}

	private static (float X, float Y, float Z) ResolveStaticPosition(
		Node positionNode, float? targetX, float? targetY, float? targetZ)
	{
		if (positionNode.X.HasValue && positionNode.Y.HasValue && positionNode.Z.HasValue)
			return (positionNode.X.Value, positionNode.Y.Value, positionNode.Z.Value);

		if (targetX.HasValue && targetY.HasValue && targetZ.HasValue)
			return (targetX.Value, targetY.Value, targetZ.Value);

		return (0f, 0f, 0f);
	}

	private static bool MatchesScene(string? candidateScene, string currentScene) =>
		string.IsNullOrEmpty(candidateScene)
			|| string.Equals(candidateScene, currentScene, StringComparison.OrdinalIgnoreCase);

	private static string? ExtractBlockedReason(SpawnCategory category, ResolvedActionSemantic semantic)
	{
		if (category == SpawnCategory.UnlockBlocked)
			return semantic.AvailabilityText;
		return null;
	}

	private static void SuppressBlockedAtOccupiedPositions(List<MarkerCandidate> candidates)
	{
		if (candidates.Count == 0)
			return;

		var occupiedByNonBlocked = new HashSet<(float, float, float)>();
		for (int i = 0; i < candidates.Count; i++)
		{
			if (IsBlocked(candidates[i]))
				continue;
			occupiedByNonBlocked.Add((candidates[i].X, candidates[i].Y, candidates[i].Z));
		}

		if (occupiedByNonBlocked.Count == 0)
			return;

		int write = 0;
		for (int read = 0; read < candidates.Count; read++)
		{
			var c = candidates[read];
			if (IsBlocked(c) && occupiedByNonBlocked.Contains((c.X, c.Y, c.Z)))
				continue;
			candidates[write++] = c;
		}
		candidates.RemoveRange(write, candidates.Count - write);
	}

	private static bool IsBlocked(MarkerCandidate c) =>
		c.QuestKind == QuestMarkerKind.QuestGiverBlocked
		|| c.SpawnCategory == SpawnCategory.UnlockBlocked;
}
