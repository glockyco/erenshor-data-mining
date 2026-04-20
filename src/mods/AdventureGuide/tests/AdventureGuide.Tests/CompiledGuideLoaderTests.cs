using AdventureGuide.CompiledGuide;
using AdventureGuide.Tests.Helpers;
using Xunit;

namespace AdventureGuide.Tests;

public sealed class CompiledGuideLoaderTests
{
    [Fact]
    public void Builder_creates_dense_quest_lookup()
    {
        var guide = new CompiledGuideBuilder()
            .AddQuest("quest:a", dbName: "QUESTA")
            .AddQuest("quest:b", dbName: "QUESTB", prereqs: new[] { "quest:a" })
            .Build();

        Assert.Equal(2, guide.NodeCount);
        Assert.Equal(2, guide.QuestCount);
        Assert.True(guide.TryGetNodeId("quest:a", out int questA));
        Assert.True(guide.TryGetNodeId("quest:b", out int questB));
        Assert.Equal("quest:a", guide.GetNodeKey(questA));
        Assert.Equal("quest:b", guide.GetNodeKey(questB));
        Assert.Equal(questA, guide.PrereqQuestIds(1)[0]);
    }

    [Fact]
    public void ParseJson_reads_minimal_json()
    {
        string json = BuildMinimalJson();

        var guide = CompiledGuideLoader.ParseJson(json);

        Assert.Equal(1, guide.NodeCount);
        Assert.Equal(0, guide.EdgeCount);
        Assert.Equal(1, guide.QuestCount);
        Assert.True(guide.TryGetNodeId("quest:a", out int nodeId));
        Assert.Equal("Quest A", guide.GetDisplayName(nodeId));
        Assert.Equal(0, guide.TopologicalOrder[0]);
    }

    [Fact]
    public void Builder_creates_giver_blueprints_for_compiled_marker_flow()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:giver", scene: "Town", x: 1f, y: 2f, z: 3f)
            .AddQuest("quest:pre", dbName: "PRE")
            .AddQuest(
                "quest:root",
                dbName: "ROOT",
                prereqs: new[] { "quest:pre" },
                givers: new[] { "char:giver" }
            )
            .Build();

        Assert.Equal(1, guide.GiverBlueprints.Length);
        Assert.True(guide.TryGetNodeId("quest:root", out int questId));
        Assert.True(guide.TryGetNodeId("char:giver", out int giverId));

        QuestGiverEntry blueprint = guide.GiverBlueprints[0];
        Assert.Equal(questId, blueprint.QuestId);
        Assert.Equal(giverId, blueprint.CharacterId);
        Assert.Equal(giverId, blueprint.PositionId);
        Assert.Equal(0, blueprint.InteractionType);
        Assert.Null(blueprint.Keyword);
        Assert.Equal(new[] { "PRE" }, blueprint.RequiredQuestDbNames);
    }

    [Fact]
    public void Builder_creates_completion_blueprints_for_compiled_marker_flow()
    {
        var guide = new CompiledGuideBuilder()
            .AddCharacter("char:turnin", scene: "Town", x: 4f, y: 5f, z: 6f)
            .AddQuest("quest:root", dbName: "ROOT", completers: new[] { "char:turnin" })
            .Build();

        Assert.Equal(1, guide.CompletionBlueprints.Length);
        Assert.True(guide.TryGetNodeId("quest:root", out int questId));
        Assert.True(guide.TryGetNodeId("char:turnin", out int turnInId));

        QuestCompletion blueprint = guide.CompletionBlueprints[0];
        Assert.Equal(questId, blueprint.QuestId);
        Assert.Equal(turnInId, blueprint.CharacterId);
        Assert.Equal(turnInId, blueprint.PositionId);
        Assert.Equal(0, blueprint.InteractionType);
        Assert.Null(blueprint.Keyword);
    }

    [Fact]
    public void ParseJson_reads_blueprint_metadata()
    {
        string json = BuildBlueprintJson();

        var guide = CompiledGuideLoader.ParseJson(json);

        Assert.True(guide.TryGetNodeId("quest:root", out int questId));
        Assert.True(guide.TryGetNodeId("char:npc", out int npcId));
        Assert.Equal(1, guide.GiverBlueprints.Length);
        Assert.Equal(1, guide.CompletionBlueprints.Length);

        QuestGiverEntry giver = guide.GiverBlueprints[0];
        Assert.Equal(questId, giver.QuestId);
        Assert.Equal(npcId, giver.CharacterId);
        Assert.Equal(npcId, giver.PositionId);
        Assert.Equal(1, giver.InteractionType);
        Assert.Equal("hail", giver.Keyword);
        Assert.Equal(new[] { "PRE", "CHAIN" }, giver.RequiredQuestDbNames);

        QuestCompletion completion = guide.CompletionBlueprints[0];
        Assert.Equal(questId, completion.QuestId);
        Assert.Equal(npcId, completion.CharacterId);
        Assert.Equal(npcId, completion.PositionId);
        Assert.Equal(1, completion.InteractionType);
        Assert.Equal("done", completion.Keyword);
    }

    private static string BuildMinimalJson()
    {
        return """
            {
                "nodes": [
                    {"node_id":0,"key":"quest:a","node_type":0,"display_name":"Quest A","scene":null,"x":null,"y":null,"z":null,"flags":0,"level":0,"zone_key":null,"db_name":null,"description":null,"keyword":null,"zone_display":null,"xp_reward":0,"gold_reward":0,"reward_item_key":null,"disabled_text":null,"key_item_key":null,"destination_zone_key":null,"destination_display":null}
                ],
                "edges": [],
                "forward_adjacency": [[]],
                "reverse_adjacency": [[]],
                "quest_node_ids": [0],
                "item_node_ids": [],
                "quest_specs": [
                    {"quest_id":0,"quest_index":0,"prereq_quest_ids":[],"prereq_quest_indices":[],"required_items":[],"steps":[],"giver_node_ids":[],"completer_node_ids":[],"chains_to_ids":[],"is_implicit":false,"is_infeasible":false,"display_name":"Quest A"}
                ],
                "item_sources": [],
                "unlock_predicates": [],
                "topo_order": [0],
                "item_to_quest_indices": [],
                "quest_to_dependent_quest_indices": [[]],
                "zone_node_ids": [],
                "zone_adjacency": [],

                "giver_blueprints": [],
                "completion_blueprints": [],
                "infeasible_node_ids": []
            }
            """;
    }

    private static string BuildBlueprintJson()
    {
        return """
            {
                "nodes": [
                    {"node_id":0,"key":"quest:root","node_type":0,"display_name":"Quest Root","scene":null,"x":null,"y":null,"z":null,"flags":0,"level":0,"zone_key":null,"db_name":"ROOT","description":null,"keyword":null,"zone_display":null,"xp_reward":0,"gold_reward":0,"reward_item_key":null,"disabled_text":null,"key_item_key":null,"destination_zone_key":null,"destination_display":null},
                    {"node_id":1,"key":"char:npc","node_type":2,"display_name":"NPC","scene":"Town","x":10.0,"y":20.0,"z":30.0,"flags":0,"level":0,"zone_key":null,"db_name":null,"description":null,"keyword":null,"zone_display":null,"xp_reward":0,"gold_reward":0,"reward_item_key":null,"disabled_text":null,"key_item_key":null,"destination_zone_key":null,"destination_display":null}
                ],
                "edges": [],
                "forward_adjacency": [[],[]],
                "reverse_adjacency": [[],[]],
                "quest_node_ids": [0],
                "item_node_ids": [],
                "quest_specs": [
                    {"quest_id":0,"quest_index":0,"prereq_quest_ids":[],"prereq_quest_indices":[],"required_items":[],"steps":[],"giver_node_ids":[],"completer_node_ids":[],"chains_to_ids":[],"is_implicit":false,"is_infeasible":false,"display_name":"Quest Root"}
                ],
                "item_sources": [],
                "unlock_predicates": [],
                "topo_order": [0],
                "item_to_quest_indices": [],
                "quest_to_dependent_quest_indices": [[]],
                "zone_node_ids": [],
                "zone_adjacency": [],

                "giver_blueprints": [
                    {"quest_id":0,"character_id":1,"position_id":1,"interaction_type":1,"keyword":"hail","required_quest_db_names":["PRE","CHAIN"]}
                ],
                "completion_blueprints": [
                    {"quest_id":0,"character_id":1,"position_id":1,"interaction_type":1,"keyword":"done"}
                ],
                "infeasible_node_ids": []
            }
            """;
    }
}
