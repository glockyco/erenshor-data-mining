using AdventureGuide.Data;
using AdventureGuide.Navigation;

namespace AdventureGuide.Tests;

public sealed class NavigationPolicyTests
{
    [Fact]
    public void Fixed_position_spec_preserves_coordinates_and_identity()
    {
        var quest = new QuestEntry
        {
            StableKey = "quest:position",
            DBName = "PositionQuest",
            DisplayName = "Position quest",
        };
        var step = new QuestStep
        {
            Order = 7,
            Action = "go_to",
            Description = "Furnish the room at the planning table.",
            TargetName = "Planning Table",
            TargetType = "location",
            TargetKey = "planningtable:point",
            Location = new StepLocation
            {
                StableKey = "planningtable:point",
                DisplayName = "Planning Table",
                Scene = "TestScene",
                X = 3f,
                Y = 4f,
                Z = 5f,
            },
        };

        var spec = NavigationPolicy.CreateFixedPositionTargetSpec(step, quest, "OriginQuest", 2);

        Assert.Equal(3f, spec.X);
        Assert.Equal(4f, spec.Y);
        Assert.Equal(5f, spec.Z);
        Assert.Equal("Planning Table", spec.DisplayName);
        Assert.Equal("TestScene", spec.Scene);
        Assert.Equal("PositionQuest", spec.QuestKey);
        Assert.Equal(7, spec.StepOrder);
        Assert.Equal("planningtable:point", spec.SourceId);
        Assert.Equal("OriginQuest", spec.OriginQuestKey);
        Assert.Equal(2, spec.OriginStepOrder);
    }

    [Fact]
    public void Euclidean_distance_uses_all_three_coordinates()
    {
        Assert.Equal(7f, NavigationPolicy.EuclideanDistance(0f, 0f, 0f, 2f, 3f, 6f));
    }

    [Fact]
    public void Fixed_position_spec_falls_back_to_description_for_target_name()
    {
        var quest = new QuestEntry { DBName = "PositionQuest" };
        var step = new QuestStep
        {
            Order = 1,
            Description = "Fallback description",
            Location = new StepLocation { Scene = "TestScene" },
        };

        var spec = NavigationPolicy.CreateFixedPositionTargetSpec(step, quest, "origin", 1);

        Assert.Equal("Fallback description", spec.DisplayName);
    }

    [Fact]
    public void Fixed_position_spec_requires_location()
    {
        var quest = new QuestEntry { DBName = "PositionQuest" };
        var step = new QuestStep { Order = 1, Description = "No location" };

        var error = Assert.Throws<ArgumentException>(() =>
            NavigationPolicy.CreateFixedPositionTargetSpec(step, quest, "origin", 1)
        );

        Assert.Equal("step", error.ParamName);
    }
}
