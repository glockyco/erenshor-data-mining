using AdventureGuide.Data;
using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class MarkerPolicyTests
{
    [Fact]
    public void Quest_giver_type_distinguishes_repeatable_quests()
    {
        Assert.Equal(MarkerType.QuestGiver, MarkerDecision.GetQuestGiverType(false));
        Assert.Equal(MarkerType.QuestGiverRepeat, MarkerDecision.GetQuestGiverType(true));
    }

    [Fact]
    public void Turn_in_type_distinguishes_ready_pending_and_repeatable_ready()
    {
        Assert.Equal(MarkerType.TurnInReady, MarkerDecision.GetTurnInType(true, false));
        Assert.Equal(MarkerType.TurnInRepeatReady, MarkerDecision.GetTurnInType(true, true));
        Assert.Equal(MarkerType.TurnInPending, MarkerDecision.GetTurnInType(false, false));
        Assert.Equal(MarkerType.TurnInPending, MarkerDecision.GetTurnInType(false, true));
    }

    [Fact]
    public void Duplicate_intent_replacement_uses_marker_priority_order()
    {
        Assert.True(MarkerDecision.ShouldReplace(MarkerType.Objective, MarkerType.TurnInReady));
        Assert.False(MarkerDecision.ShouldReplace(MarkerType.TurnInReady, MarkerType.Objective));
        Assert.False(MarkerDecision.ShouldReplace(MarkerType.Objective, MarkerType.Objective));
    }

    [Theory]
    [InlineData("talk", null, null, "Talk to")]
    [InlineData("talk", "Open sesame", null, "Say 'Open sesame'")]
    [InlineData("shout", null, null, "Shout near")]
    [InlineData("shout", "Stay back", null, "Shout 'Stay back'")]
    [InlineData("kill", null, 1, "Kill")]
    [InlineData("kill", null, 3, "Kill (3)")]
    [InlineData("turn_in", null, null, "Turn in")]
    [InlineData("buy", null, null, "Buy")]
    [InlineData("loot", null, null, "Loot")]
    [InlineData("unknown", null, null, "Talk to")]
    public void Step_action_text_describes_action_and_keyword(
        string action,
        string? keyword,
        int? quantity,
        string expected
    )
    {
        var step = new QuestStep
        {
            Action = action,
            Keyword = keyword,
            Quantity = quantity,
        };

        Assert.Equal(expected, MarkerTextFormatter.FormatStepActionText(step));
    }

    [Fact]
    public void Turn_in_text_without_required_items_uses_talk_or_keyword()
    {
        var quest = new QuestEntry();

        Assert.Equal(
            "Talk to",
            MarkerTextFormatter.FormatTurnInText(quest, new CompletionSource())
        );
        Assert.Equal(
            "Say 'FIRE'",
            MarkerTextFormatter.FormatTurnInText(quest, new CompletionSource { Keyword = "FIRE" })
        );
    }

    [Fact]
    public void Turn_in_text_with_one_required_item_names_the_item()
    {
        var quest = new QuestEntry
        {
            RequiredItems =
            [
                new RequiredItemInfo { ItemName = "Dragon Scale", ItemStableKey = "item:scale" },
            ],
        };

        Assert.Equal(
            "Give Dragon Scale",
            MarkerTextFormatter.FormatTurnInText(quest, new CompletionSource())
        );
    }

    [Fact]
    public void Turn_in_text_with_multiple_required_items_reports_the_count()
    {
        var quest = new QuestEntry
        {
            RequiredItems =
            [
                new RequiredItemInfo { ItemName = "Dragon Scale", ItemStableKey = "item:scale" },
                new RequiredItemInfo { ItemName = "Dragon Claw", ItemStableKey = "item:claw" },
            ],
        };

        Assert.Equal(
            "Give 2 items",
            MarkerTextFormatter.FormatTurnInText(quest, new CompletionSource())
        );
    }

    [Fact]
    public void Turn_in_text_ignores_or_group_alternatives()
    {
        var quest = new QuestEntry
        {
            RequiredItems =
            [
                new RequiredItemInfo
                {
                    ItemName = "Red Herb",
                    ItemStableKey = "item:red-herb",
                    OrGroup = "herb",
                },
                new RequiredItemInfo
                {
                    ItemName = "Blue Herb",
                    ItemStableKey = "item:blue-herb",
                    OrGroup = "herb",
                },
            ],
        };

        Assert.Equal(
            "Talk to",
            MarkerTextFormatter.FormatTurnInText(quest, new CompletionSource())
        );
    }
}
