---
name: unity-export-system
description: C# export pipeline architecture and adding new export types. Use when working on asset scanners, listeners, database records, or the export code in src/Assets/Editor/.
---

# Unity Export System

The export system scans Unity assets and writes structured data to SQLite.

## Architecture

```
AssetScanner
├── Scans Unity project for assets
├── Notifies registered listeners
└── Listeners write to SQLite

ExportBatch.cs (entry point)
├── Opens SQLite connection
├── Registers all listeners
├── Triggers asset scan
└── Closes connection
```

**Location**: `src/Assets/Editor/ExportSystem/`

| File | Purpose |
|------|---------|
| ExportBatch.cs | Batch mode entry point, listener registration |
| AssetScanner.cs | Scans assets, notifies listeners |
| Repository.cs | Database operations |

## Listeners

Each listener implements `IAssetScanListener<T>` to extract specific game data.

Located in `src/Assets/Editor/ExportSystem/AssetScanner/Listener/`. Find all with: `ls` the directory.

Listener categories: core entities (items, characters, spells, skills), game systems (quests, spawns, loot, teleports), and auxiliary data (books, factions, achievements, etc.).

## Database Records

Record classes define SQLite table schemas via `[Table]` attribute. Located in `src/Assets/Editor/Database/`.

Junction tables handle many-to-many relationships (e.g., `CharacterAttackSpells`, `QuestRequiredItems`, `ItemClasses`, `SpawnPointCharacters`). Find all record classes by listing the directory.

## StableKey System

Entities use stable keys for consistent identification across exports:

```csharp
// Items: "item:resource_name"
StableKeyGenerator.ForItem(item)

// Characters (prefab): "character:object_name"
// Characters (placed): "character:object_name|scene|x|y|z"
StableKeyGenerator.ForCharacter(character)

// Spells: "spell:resource_name"
StableKeyGenerator.ForSpell(spell)
```

## Adding a New Export Type

### 1. Create a record class

`src/Assets/Editor/Database/MyRecord.cs`:

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

### 2. Create a listener

`src/Assets/Editor/ExportSystem/AssetScanner/Listener/MyListener.cs`:

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

### 3. Register in ExportBatch.cs

In the `RegisterListeners` method, add a registration entry:

```csharp
// Choose the appropriate registration method:
["mytype"] = () => scanner.RegisterScriptableObjectListener(new MyListener(db)),
// or: scanner.RegisterComponentListener(...)
// or: scanner.RegisterGameObjectListener(...)
// or: scanner.RegisterNullListener(...) for special processing
```

### 4. Test

`uv run erenshor extract export`

## Key Patterns

- Use `StableKeyGenerator` for consistent primary keys (follow existing `For*` method conventions)
- Batch inserts in transactions for performance
- Clear lists after insertion to free memory
- Junction tables for many-to-many relationships (separate record class per relationship)

## Running Exports

```bash
# Full export via CLI
uv run erenshor extract export

# Or via Unity batch mode directly
Unity -batchmode -projectPath variants/main/unity \
  -executeMethod ExportBatch.Run -logFile export.log -quit
```
