using AdventureGuide.Data;

namespace AdventureGuide.Tests;

public sealed class NavigationSceneTests
{
    [Fact]
    public void Character_candidates_include_later_spawn_scenes()
    {
        var data = GuideData.FromWrapper(
            new GuideWrapper
            {
                Version = 6,
                Quests = [],
                CharacterSpawns = new Dictionary<string, List<SpawnPoint>>
                {
                    ["character:brown bear cub"] =
                    [
                        new SpawnPoint { Scene = "Brake" },
                        new SpawnPoint { Scene = "Stowaway" },
                    ],
                },
            }
        );
        var step = new QuestStep
        {
            TargetType = "character",
            TargetKey = "character:brown bear cub",
        };
        var quest = new QuestEntry();
        Assert.True(StepSceneResolver.HasSourceInScene(quest, step, data, "Stowaway"));
        Assert.True(StepSceneResolver.HasSourceInScene(quest, step, data, "brake"));
        Assert.False(StepSceneResolver.HasSourceInScene(quest, step, data, "Hidden"));
    }
}
