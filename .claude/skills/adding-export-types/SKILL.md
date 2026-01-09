---
name: adding-export-types
description: Add new Unity export types to extract game data. Use when adding new data extractors, listeners, or database tables for the data mining pipeline.
---

# Adding New Export Types

Export types extract specific game data from Unity assets to SQLite.

## Steps

1. **Create record class**: `src/Assets/Editor/Database/MyRecord.cs`

```csharp
using SQLite;

[Table("MyTable")]
public class MyRecord
{
    [PrimaryKey]
    public string StableKey { get; set; }

    public string Name { get; set; }
    public int Value { get; set; }
}
```

2. **Create listener**: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/MyListener.cs`

```csharp
public class MyListener : IAssetScanListener<MyUnityType>
{
    private readonly SQLiteConnection _db;
    private readonly List<MyRecord> _records = new();

    public MyListener(SQLiteConnection db) => _db = db;

    public void OnAssetFound(MyUnityType asset)
    {
        _records.Add(new MyRecord
        {
            StableKey = StableKeyGenerator.ForMyType(asset),
            Name = asset.name,
            Value = asset.value
        });
    }

    public void OnScanFinished()
    {
        _db.CreateTable<MyRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<MyRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }
}
```

3. **Register in ExportBatch.cs** (in `RegisterListeners` method):

```csharp
// Choose the appropriate registration method:
["mytype"] = () => scanner.RegisterScriptableObjectListener(new MyListener(db)),
// or: scanner.RegisterComponentListener(...)
// or: scanner.RegisterGameObjectListener(...)
// or: scanner.RegisterNullListener(...) for special processing
```

4. **Test**: `uv run erenshor extract export`

## Key Patterns

- Use `StableKeyGenerator` for consistent primary keys
- Batch inserts in transactions for performance
- Clear lists after insertion to free memory
- Junction tables for many-to-many relationships

## Existing Listeners (25 total)

Located in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/`:
- **Core**: ItemListener, CharacterListener, SpellListener, SkillListener
- **Quests**: QuestListener, AchievementTriggerListener
- **World**: SpawnPointListener, LootTableListener, TeleportLocListener
- **Resources**: MiningNodeListener, TreasureLocListener, WishingWellListener
- **Other**: BookListener, ClassListener, WorldFactionListener, AscensionListener, etc.
