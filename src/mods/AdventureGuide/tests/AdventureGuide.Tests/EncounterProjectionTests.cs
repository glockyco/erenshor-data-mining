using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace AdventureGuide.Tests;

[Collection("Game state")]
public sealed class EncounterProjectionTests : IDisposable
{
    private const string ClaimQuest = "quest:claim";
    private const string Encounter = "encounter:claim";
    private const string Root = "spawn:0";

    public EncounterProjectionTests() => ResetGameState();

    public void Dispose() => ResetGameState();

    [Theory]
    [InlineData(false, false, QuestRuntimeStatus.Available, true)]
    [InlineData(true, false, QuestRuntimeStatus.Completed, false)]
    [InlineData(false, true, QuestRuntimeStatus.Completed, false)]
    [InlineData(true, true, QuestRuntimeStatus.Completed, false)]
    public void Claim_state_projects_before_awake_without_changing_raw_quest_state(
        bool claimed,
        bool completed,
        QuestRuntimeStatus status,
        bool available
    )
    {
        var data = Data();
        var game = new Snapshot { AccountClaimed = claimed };
        if (completed)
            game.Completed.Add("CLAIM");
        var state = new QuestStateTracker(data, new EntityRegistry(), game);
        state.SyncFromGameData();
        var quest = data.GetByStableKey(ClaimQuest)!;

        Assert.Equal(status, state.GetStatus(quest));
        Assert.Equal(available, state.Gates.IsAvailable(0));
        Assert.Equal(available, state.Gates.CanBecomeAvailable(0));
        Assert.Equal(completed, state.IsGameQuestCompleted("CLAIM"));
        Assert.Equal(completed, state.CompletedQuests.Contains("CLAIM"));
        Assert.Equal(claimed, game.AccountClaimed);
        Assert.Equal(completed, game.Completed.Contains("CLAIM"));
        Assert.Equal(
            status == QuestRuntimeStatus.Completed ? quest.Steps!.Count : 0,
            StepProgress.GetCurrentStepIndex(quest, state, data)
        );
    }

    [Fact]
    public void Account_completion_precedes_active_and_implicit_presentation_only_for_bound_quests()
    {
        var wrapper = Wrapper();
        wrapper.Quests![0].Acceptance = "implicit";
        wrapper.Quests[0].Steps![0].ZoneName = "Test area";
        wrapper.ZoneLookup = new()
        {
            ["TestScene"] = new ZoneInfo { StableKey = "zone:test", DisplayName = "Test area" },
        };
        wrapper.Quests.Add(Quest("quest:ordinary", "ORDINARY"));
        var data = GuideData.FromWrapper(wrapper);
        var game = new Snapshot { AccountClaimed = true };
        game.Active.UnionWith(["CLAIM", "ORDINARY"]);
        game.Completed.Add("ORDINARY");
        var state = new QuestStateTracker(data, new EntityRegistry(), game);
        state.OnSceneChanged("TestScene");

        Assert.Equal(QuestRuntimeStatus.Completed, state.GetStatus(data.GetByDBName("CLAIM")!));
        Assert.Equal(QuestRuntimeStatus.Active, state.GetStatus(data.GetByDBName("ORDINARY")!));
        Assert.True(state.IsGameQuestActive("CLAIM"));
        Assert.False(state.IsGameQuestCompleted("CLAIM"));
        Assert.Contains("CLAIM", state.ActiveQuests);
        Assert.DoesNotContain("CLAIM", state.CompletedQuests);
        game.Active.Remove("CLAIM");
        game.AccountClaimed = false;
        state.SyncFromGameData();
        Assert.Equal(
            QuestRuntimeStatus.ImplicitlyActive,
            state.GetStatus(data.GetByDBName("CLAIM")!)
        );
        game.AccountClaimed = true;
        state.Update(0);
        Assert.Equal(QuestRuntimeStatus.Completed, state.GetStatus(data.GetByDBName("CLAIM")!));
    }

    [Fact]
    public void Host_death_outcome_is_not_a_current_state_or_initialization_rule()
    {
        var wrapper = Wrapper();
        var data = GuideData.FromWrapper(wrapper);
        var facts = new GateTestFacts();
        var gates = new GateConditions(data, facts);

        Assert.True(gates.IsAvailable(0));
        Assert.False(gates.IsProjectedQuestCompleted(data.GetByDBName("CLAIM")!));
        Assert.Equal(
            "false",
            data.Encounters.Conditions.Single(row => row.StateScope == "account").RequiredValue
        );
        Assert.Equal(
            "true",
            data.Encounters.Completions.Single(row =>
                row.EventKind == "host_death" && row.StateScope == "account"
            ).ResultValue
        );
        facts.AccountClaimed = true;
        Assert.False(gates.IsAvailable(0));
    }

    [Fact]
    public void Four_support_placement_keys_survive_json_without_prefab_deduplication()
    {
        string json = JsonConvert.SerializeObject(Wrapper());
        var data = GuideData.Parse(json);
        var gates = new GateConditions(data, new GateTestFacts());
        Assert.True(gates.IsAvailable(0));
        Assert.Equal("false", data.Conditions[0][0][0].Value);
        Assert.Contains(
            data.Encounters.Completions,
            row =>
                row.EventKind == "host_death"
                && row.StateScope == "account"
                && row.ResultValue == "true"
        );
        Assert.Equal(
            new[] { "spawn:0", "spawn:1", "spawn:2", "spawn:3", "spawn:4" },
            data.Encounters.Placements.Select(row => row.MemberSpawnStableKey)
        );
        Assert.Equal(4, data.Encounters.Placements.Count(row => row.Role == "support"));
        Assert.All(
            data.Encounters.Placements,
            row =>
            {
                Assert.Equal(Root, row.RootSpawnStableKey);
                Assert.Equal("account_claim", row.ContextKind);
                Assert.Equal("player_home", row.PostCompletionRole);
            }
        );
        var payload = JObject.Parse(json)["_encounters"]!;
        foreach (
            string family in new[]
            {
                "encounter_conditions",
                "encounter_completions",
                "encounter_event_conditions",
            }
        )
            Assert.All(
                (JArray)payload[family]!,
                row =>
                {
                    Assert.Null(row["context_kind"]);
                    Assert.Null(row["post_completion_role"]);
                }
            );
    }

    [Fact]
    public void Schema_eight_rejects_missing_encounter_contract()
    {
        var payload = JObject.FromObject(Wrapper());
        payload.Remove("_encounters");
        Assert.Throws<InvalidDataException>(() => GuideData.Parse(payload.ToString()));
        payload = JObject.FromObject(Wrapper());
        ((JObject)payload["_encounters"]!).Remove("encounter_event_conditions");
        Assert.Throws<JsonSerializationException>(() => GuideData.Parse(payload.ToString()));
    }

    [Theory]
    [InlineData("false_guard")]
    [InlineData("false_effect")]
    [InlineData("wrong_scope")]
    [InlineData("missing_guard")]
    [InlineData("unknown_event")]
    [InlineData("unbound_guard")]
    [InlineData("unknown_account")]
    [InlineData("missing_host_death")]
    [InlineData("missing_awake_effect")]
    [InlineData("missing_condition")]
    [InlineData("false_host_death")]
    public void Incomplete_or_unsupported_encounter_contracts_fail_load(string mutation)
    {
        var wrapper = Wrapper();
        var context = wrapper.Encounters!;
        switch (mutation)
        {
            case "false_guard":
                context.EventConditions[0].RequiredValue = "false";
                break;
            case "false_effect":
                context.Completions[2].ResultValue = "false";
                break;
            case "wrong_scope":
                context.EventConditions[0].StateScope = "account";
                context.EventConditions[0].StateKey = EncounterStateKeys.ReliquaryClaimed;
                break;
            case "missing_guard":
                context.EventConditions.RemoveAt(0);
                break;
            case "unknown_event":
                context.Completions[2].EventKind = "scene_start";
                break;
            case "unbound_guard":
                context.EventConditions[0].EncounterKey = "encounter:absent";
                break;
            case "unknown_account":
                context.Conditions[0].StateKey = "account_state:absent";
                break;
            case "missing_host_death":
                context.Completions.RemoveAt(0);
                break;
            case "missing_awake_effect":
                context.Completions.RemoveAt(2);
                break;
            case "missing_condition":
                context.Conditions.RemoveAt(0);
                break;
            case "false_host_death":
                context.Completions[0].ResultValue = "false";
                break;
        }
        Assert.Throws<InvalidDataException>(() => GuideData.FromWrapper(wrapper));
    }

    [Theory]
    [InlineData("actor", null)]
    [InlineData("actor", "player")]
    [InlineData("value", null)]
    [InlineData("value", "False")]
    [InlineData("phase", null)]
    [InlineData("phase", "operation_outcome")]
    [InlineData("scope", null)]
    [InlineData("scope", " ")]
    [InlineData("ref", "account_state:unknown")]
    public void Account_availability_rejects_missing_or_unsupported_semantics(
        string field,
        string? value
    )
    {
        var payload = JObject.FromObject(Wrapper());
        var atom = (JObject)payload["_conditions"]![0]![0]![0]!;
        if (value == null)
            atom.Remove(field);
        else
            atom[field] = value;
        Assert.Throws<InvalidDataException>(() => GuideData.Parse(payload.ToString()));
    }

    [Fact]
    public void Primitive_changes_invalidate_once_and_expose_current_typed_reads()
    {
        var game = new Snapshot();
        var state = new QuestStateTracker(Data(), new EntityRegistry(), game);
        int events = 0;
        int eventVersion = -1;
        state.PrimitiveStateChanged += () =>
        {
            events++;
            eventVersion = state.Version;
        };
        int before = state.Version;
        game.AccountClaimed = true;
        game.ReturnZone = "ZoneA";
        game.ReturnLanding = new Vector3(1, 2, 3);
        game.PlayerLevel = 12;
        state.Update(0);

        Assert.Equal(before + 1, state.Version);
        Assert.Equal(state.Version, eventVersion);
        Assert.Equal(1, events);
        Assert.True(state.Gates.Facts.ReadAccountState(EncounterStateKeys.ReliquaryClaimed));
        Assert.Equal(
            "ZoneA",
            state.Gates.Facts.ReadCharacterZoneState(EncounterStateKeys.ReturnZone)
        );
        Assert.Equal(
            3,
            state.Gates.Facts.ReadCharacterPositionState(EncounterStateKeys.ReturnLanding)!.Value.z
        );
        Assert.Equal(12, state.Gates.Facts.PlayerLevel);
        state.Update(0);
        Assert.Equal(before + 1, state.Version);
        Assert.Equal(1, events);
        game.PlayerLevel = 13;
        state.Update(0);
        Assert.Equal(before + 2, state.Version);
        Assert.Equal(2, events);
    }

    [Fact]
    public void Character_load_changes_projection_and_return_state_with_one_invalidation()
    {
        var game = new Snapshot { ReturnZone = "ZoneA", ReturnLanding = new Vector3(1, 2, 3) };
        game.Completed.Add("CLAIM");
        var data = Data();
        var state = new QuestStateTracker(data, new EntityRegistry(), game);
        state.OnCharacterLoaded();
        Assert.True(state.IsCompleted(data.GetByDBName("CLAIM")!));
        int events = 0;
        state.PrimitiveStateChanged += () => events++;
        int version = state.Version;
        game.Completed.Clear();
        game.ReturnZone = "ZoneB";
        game.ReturnLanding = new Vector3(4, 5, 6);
        state.OnCharacterLoaded();

        Assert.Equal(version + 1, state.Version);
        Assert.Equal(1, events);
        Assert.False(state.IsCompleted(data.GetByDBName("CLAIM")!));
        Assert.Equal("ZoneB", state.ReadCharacterZoneState(EncounterStateKeys.ReturnZone));
        Assert.Empty(state.CompletedQuests);
        state.Update(0);
        Assert.Equal(1, events);
    }

    [Fact]
    public void Unchanged_primitive_polling_is_allocation_free_after_warmup()
    {
        var state = new QuestStateTracker(
            Data(),
            new EntityRegistry(),
            new Snapshot { ReturnZone = "ZoneA", ReturnLanding = new Vector3(float.NaN, 2, 3) }
        );
        for (int i = 0; i < 64; i++)
            state.Update(0);
        int version = state.Version;
        long before = GC.GetAllocatedBytesForCurrentThread();
        for (int i = 0; i < 128; i++)
            state.Update(0);
        long allocated = GC.GetAllocatedBytesForCurrentThread() - before;
        Assert.Equal(0L, allocated);
        Assert.Equal(version, state.Version);
    }

    [Fact]
    public void Live_state_reader_uses_loaded_primitives_without_world_entry_or_save_loading()
    {
        GameData.AccountClaimedReliquary = true;
        GameData.ReliqDest = "ZoneA";
        GameData.ReliqLanding = new Vector3(4, 5, 6);
        GameData.PlayerStats = new Stats { Level = 17 };
        var live = LiveQuestGameState.Instance;
        Assert.True(live.ReadAccountState(EncounterStateKeys.ReliquaryClaimed));
        Assert.Equal("ZoneA", live.ReadCharacterZoneState(EncounterStateKeys.ReturnZone));
        Assert.Equal(6, live.ReadCharacterPositionState(EncounterStateKeys.ReturnLanding)!.Value.z);
        Assert.Equal(17, live.PlayerLevel);
        Assert.Throws<ArgumentException>(() => live.ReadAccountState("account_state:absent"));
        Assert.Throws<ArgumentException>(() =>
            live.ReadCharacterZoneState("character_state:absent")
        );
        Assert.Throws<ArgumentException>(() =>
            live.ReadCharacterPositionState("character_state:absent")
        );
    }

    [Fact]
    public void Live_quest_and_inventory_mirrors_remain_raw_when_the_account_is_claimed()
    {
        GameData.AccountClaimedReliquary = true;
        GameData.HasQuest = ["CLAIM"];
        GameData.CompletedQuests = ["OTHER"];
        GameData.PlayerInv = new PlanningInventory
        {
            StoredSlots =
            [
                new ItemIcon
                {
                    MyItem = new Item { name = "Key", RequiredSlot = Item.SlotType.General },
                    Quantity = 3,
                },
            ],
        };
        var data = Data();
        var state = new QuestStateTracker(data, new EntityRegistry());
        state.SyncFromGameData();

        Assert.True(state.IsCompleted(data.GetByDBName("CLAIM")!));
        Assert.True(state.IsGameQuestActive("CLAIM"));
        Assert.False(state.IsGameQuestCompleted("CLAIM"));
        Assert.Equal(new[] { "OTHER" }, state.CompletedQuests);
        Assert.Equal(3, state.CountItem("item:key"));
        Assert.DoesNotContain("CLAIM", GameData.CompletedQuests);
        Assert.Contains("CLAIM", GameData.HasQuest);
    }

    private static GuideData Data() => GuideData.FromWrapper(Wrapper());

    private static GuideWrapper Wrapper() =>
        new()
        {
            Version = 8,
            ZoneLineDestinationContexts = [],
            Quests = [Quest(ClaimQuest, "CLAIM")],
            Conditions =
            [
                [
                    [
                        new GateAtom
                        {
                            Kind = GateAtomKind.AccountState,
                            Ref = EncounterStateKeys.ReliquaryClaimed,
                            Actor = "account",
                            Value = "false",
                            Phase = "availability",
                            Scope = Root,
                        },
                    ],
                ],
            ],
            Encounters = new EncounterContext
            {
                Placements = Enumerable
                    .Range(0, 5)
                    .Select(i => new EncounterPlacement
                    {
                        EncounterKey = Encounter,
                        RootSpawnStableKey = Root,
                        MemberSpawnStableKey = $"spawn:{i}",
                        Role = i == 0 ? "root" : "support",
                        ContextKind = "account_claim",
                        PostCompletionRole = "player_home",
                    })
                    .ToList(),
                Conditions =
                [
                    new()
                    {
                        EncounterKey = Encounter,
                        StateScope = "account",
                        StateKey = EncounterStateKeys.ReliquaryClaimed,
                        RequiredValue = "false",
                    },
                    new()
                    {
                        EncounterKey = Encounter,
                        StateScope = "character",
                        StateKey = ClaimQuest,
                        RequiredValue = "false",
                    },
                ],
                Completions =
                [
                    new()
                    {
                        EncounterKey = Encounter,
                        EventKind = "host_death",
                        StateScope = "account",
                        StateKey = EncounterStateKeys.ReliquaryClaimed,
                        ResultValue = "true",
                    },
                    new()
                    {
                        EncounterKey = Encounter,
                        EventKind = "host_death",
                        StateScope = "character",
                        StateKey = ClaimQuest,
                        ResultValue = "true",
                    },
                    new()
                    {
                        EncounterKey = Encounter,
                        EventKind = "scene_awake_quest_completed",
                        StateScope = "account",
                        StateKey = EncounterStateKeys.ReliquaryClaimed,
                        ResultValue = "true",
                    },
                    new()
                    {
                        EncounterKey = Encounter,
                        EventKind = "scene_awake_account_claimed",
                        StateScope = "character",
                        StateKey = ClaimQuest,
                        ResultValue = "true",
                    },
                ],
                EventConditions =
                [
                    new()
                    {
                        EncounterKey = Encounter,
                        EventKind = "scene_awake_quest_completed",
                        StateScope = "character",
                        StateKey = ClaimQuest,
                        RequiredValue = "true",
                    },
                    new()
                    {
                        EncounterKey = Encounter,
                        EventKind = "scene_awake_account_claimed",
                        StateScope = "account",
                        StateKey = EncounterStateKeys.ReliquaryClaimed,
                        RequiredValue = "true",
                    },
                ],
            },
        };

    private static QuestEntry Quest(string key, string dbName) =>
        new()
        {
            StableKey = key,
            DBName = dbName,
            DisplayName = dbName,
            Steps =
            [
                new QuestStep
                {
                    Order = 1,
                    Action = "kill",
                    Description = "Defeat the encounter.",
                },
            ],
        };

    private sealed class Snapshot : IQuestGameState
    {
        public HashSet<string> Active { get; } = new(StringComparer.OrdinalIgnoreCase);
        public HashSet<string> Completed { get; } = new(StringComparer.OrdinalIgnoreCase);
        public Dictionary<string, int> Inventory { get; } = new(StringComparer.OrdinalIgnoreCase);
        public bool AccountClaimed { get; set; }
        public string? ReturnZone { get; set; }
        public Vector3? ReturnLanding { get; set; }
        public int PlayerLevel { get; set; }
        public Vector3? PlayerPosition => null;

        public void CopyActiveQuestsTo(HashSet<string> destination) =>
            destination.UnionWith(Active);

        public void CopyCompletedQuestsTo(HashSet<string> destination) =>
            destination.UnionWith(Completed);

        public void CopyInventoryCountsTo(Dictionary<string, int> destination)
        {
            foreach (var item in Inventory)
                destination[item.Key] = item.Value;
        }

        public bool ReadAccountState(string key) =>
            key == EncounterStateKeys.ReliquaryClaimed
                ? AccountClaimed
                : throw new ArgumentException(key, nameof(key));

        public string? ReadCharacterZoneState(string key) =>
            key == EncounterStateKeys.ReturnZone
                ? ReturnZone
                : throw new ArgumentException(key, nameof(key));

        public Vector3? ReadCharacterPositionState(string key) =>
            key == EncounterStateKeys.ReturnLanding
                ? ReturnLanding
                : throw new ArgumentException(key, nameof(key));
    }

    private static void ResetGameState()
    {
        GameData.AccountClaimedReliquary = false;
        GameData.ReliqDest = null;
        GameData.ReliqLanding = default;
        GameData.PlayerStats = null;
        GameData.Keyring = null;
        GameData.GM = null;
        GameData.PlayerControl = null;
        GameData.CurrentCharacterSlot = null;
        GameData.PlanningUI = null;
        GameData.PlayerInv = null;
        GameData.HasQuest = null;
        GameData.CompletedQuests = null;
    }
}
