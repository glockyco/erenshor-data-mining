using InteractiveMapCompanion.Entities;
using Xunit;

namespace InteractiveMapCompanion.Tests.Entities;

public class EntityTrackerTests
{
    private sealed class MockCharacter
    {
        public int Id { get; set; }
        public string Name { get; set; } = "";
        public EntityType? Type { get; set; }
    }

    [Fact]
    public void GetTrackedEntities_ReturnsEmpty_WhenNoCharactersFound()
    {
        var tracker = new EntityTracker<MockCharacter>(
            findEntities: () => [],
            classify: _ => EntityType.Player,
            extract: (c, t) => new EntityData(c.Id, "player", c.Name, [0, 0, 0], 0),
            shouldTrack: _ => true
        );

        var result = tracker.GetTrackedEntities();

        Assert.Empty(result);
    }

    [Fact]
    public void GetTrackedEntities_ReturnsEntities_WhenCharactersFound()
    {
        var characters = new[]
        {
            new MockCharacter
            {
                Id = 1,
                Name = "Player",
                Type = EntityType.Player,
            },
            new MockCharacter
            {
                Id = 2,
                Name = "Enemy",
                Type = EntityType.NpcEnemy,
            },
        };

        var tracker = new EntityTracker<MockCharacter>(
            findEntities: () => characters,
            classify: c => c.Type,
            extract: (c, t) => new EntityData(c.Id, t.ToString(), c.Name, [0, 0, 0], 0),
            shouldTrack: _ => true
        );

        var result = tracker.GetTrackedEntities();

        Assert.Equal(2, result.Count);
    }

    [Fact]
    public void GetTrackedEntities_ExcludesNullClassification()
    {
        var characters = new[]
        {
            new MockCharacter
            {
                Id = 1,
                Name = "Player",
                Type = EntityType.Player,
            },
            new MockCharacter
            {
                Id = 2,
                Name = "MiningNode",
                Type = null,
            }, // Excluded
        };

        var tracker = new EntityTracker<MockCharacter>(
            findEntities: () => characters,
            classify: c => c.Type,
            extract: (c, t) => new EntityData(c.Id, t.ToString(), c.Name, [0, 0, 0], 0),
            shouldTrack: _ => true
        );

        var result = tracker.GetTrackedEntities();

        Assert.Single(result);
        Assert.Equal("Player", result[0].Name);
    }

    [Fact]
    public void GetTrackedEntities_AppliesFilter()
    {
        var characters = new[]
        {
            new MockCharacter
            {
                Id = 1,
                Name = "Player",
                Type = EntityType.Player,
            },
            new MockCharacter
            {
                Id = 2,
                Name = "Enemy",
                Type = EntityType.NpcEnemy,
            },
            new MockCharacter
            {
                Id = 3,
                Name = "SimPlayer",
                Type = EntityType.SimPlayer,
            },
        };

        // Only track Player type
        var tracker = new EntityTracker<MockCharacter>(
            findEntities: () => characters,
            classify: c => c.Type,
            extract: (c, t) => new EntityData(c.Id, t.ToString(), c.Name, [0, 0, 0], 0),
            shouldTrack: t => t == EntityType.Player
        );

        var result = tracker.GetTrackedEntities();

        Assert.Single(result);
        Assert.Equal("Player", result[0].Name);
    }

    [Fact]
    public void GetTrackedEntities_ExtractsCorrectData()
    {
        var characters = new[]
        {
            new MockCharacter
            {
                Id = 42,
                Name = "TestPlayer",
                Type = EntityType.Player,
            },
        };

        var tracker = new EntityTracker<MockCharacter>(
            findEntities: () => characters,
            classify: c => c.Type,
            extract: (c, t) =>
                new EntityData(
                    Id: c.Id,
                    EntityType: "player",
                    Name: c.Name,
                    Position: [1.0f, 2.0f, 3.0f],
                    Rotation: 90.0f
                ),
            shouldTrack: _ => true
        );

        var result = tracker.GetTrackedEntities();

        Assert.Single(result);
        var entity = result[0];
        Assert.Equal(42, entity.Id);
        Assert.Equal("player", entity.EntityType);
        Assert.Equal("TestPlayer", entity.Name);
        Assert.Equal([1.0f, 2.0f, 3.0f], entity.Position);
        Assert.Equal(90.0f, entity.Rotation);
    }

    [Fact]
    public void GetTrackedEntities_TracksMultipleEntityTypes()
    {
        var characters = new[]
        {
            new MockCharacter
            {
                Id = 1,
                Name = "Player",
                Type = EntityType.Player,
            },
            new MockCharacter
            {
                Id = 2,
                Name = "Enemy1",
                Type = EntityType.NpcEnemy,
            },
            new MockCharacter
            {
                Id = 3,
                Name = "Enemy2",
                Type = EntityType.NpcEnemy,
            },
            new MockCharacter
            {
                Id = 4,
                Name = "Friendly",
                Type = EntityType.NpcFriendly,
            },
        };

        // Track Player and NpcEnemy
        var tracker = new EntityTracker<MockCharacter>(
            findEntities: () => characters,
            classify: c => c.Type,
            extract: (c, t) => new EntityData(c.Id, t.ToString(), c.Name, [0, 0, 0], 0),
            shouldTrack: t => t is EntityType.Player or EntityType.NpcEnemy
        );

        var result = tracker.GetTrackedEntities();

        Assert.Equal(3, result.Count);
        Assert.Contains(result, e => e.Name == "Player");
        Assert.Contains(result, e => e.Name == "Enemy1");
        Assert.Contains(result, e => e.Name == "Enemy2");
        Assert.DoesNotContain(result, e => e.Name == "Friendly");
    }
}
