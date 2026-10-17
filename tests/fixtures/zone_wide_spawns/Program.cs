using System.Text.Json;
using UnityEngine;

var db = new SQLite.SQLiteConnection();
var listener = new ZoneWideSpawnListener(db, new CharacterStableKeyResolver());
var first = new GameObject { name = "first" };
var second = new GameObject { name = "second" };
var source = new Misc { SivakayanSpectres = [first, second, first] };
listener.OnScanStarted();
listener.OnAssetFound(new Misc { gameObject = new GameObject { Prefab = true } });
listener.OnAssetFound(new Misc { gameObject = new GameObject { ValidScene = false } });
listener.OnAssetFound(source);
listener.OnScanFinished();
var rows = db.Rows.ToArray();
listener.OnScanStarted();
listener.OnAssetFound(new Misc { SivakayanSpectres = [second] });
listener.OnScanFinished();
var replacement = db.Rows.ToArray();
string Failure(Action<ZoneWideSpawnListener> scan)
{
    var candidate = new ZoneWideSpawnListener(
        new SQLite.SQLiteConnection(),
        new CharacterStableKeyResolver()
    );
    candidate.OnScanStarted();
    try
    {
        scan(candidate);
        candidate.OnScanFinished();
        throw new Exception("Expected invalid source to fail");
    }
    catch (InvalidOperationException error)
    {
        return error.Message;
    }
}
Console.WriteLine(
    JsonSerializer.Serialize(
        new
        {
            rows,
            replacement,
            failures = new[]
            {
                Failure(_ => { }),
                Failure(value =>
                {
                    value.OnAssetFound(source);
                    value.OnAssetFound(source);
                }),
                Failure(value => value.OnAssetFound(new Misc())),
                Failure(value => value.OnAssetFound(new Misc { SivakayanSpectres = [null] })),
                Failure(value =>
                    value.OnAssetFound(
                        new Misc { SivakayanSpectres = [new GameObject { HasCharacter = false }] }
                    )
                ),
            },
        }
    )
);

namespace SQLite
{
    public sealed class TableAttribute(string name) : Attribute { }

    public sealed class PrimaryKeyAttribute : Attribute { }

    public sealed class SQLiteConnection
    {
        public List<ZoneWideSpawnCandidateRecord> Rows = new();

        public void CreateTable<T>() { }

        public void DeleteAll<T>() => Rows.Clear();

        public void InsertAll(IEnumerable<ZoneWideSpawnCandidateRecord> rows) =>
            Rows.AddRange(rows);

        public void RunInTransaction(Action action) => action();
    }
}

namespace UnityEngine
{
    public sealed class Scene(bool valid)
    {
        public bool IsValid() => valid;
    }

    public class Component
    {
        public GameObject gameObject = new();
    }

    public sealed class GameObject
    {
        public string name = "";
        public bool Prefab;
        public bool ValidScene = true;
        public bool HasCharacter = true;
        public Scene scene => new(ValidScene);

        public T? GetComponent<T>()
            where T : Component => HasCharacter ? new Character { gameObject = this } as T : null;
    }
}

namespace UnityEditor
{
    public static class PrefabUtility
    {
        public static bool IsPartOfPrefabAsset(Component component) => component.gameObject.Prefab;
    }
}

public interface IAssetScanListener<T> { }

public sealed class Misc : Component
{
    public List<GameObject?> SivakayanSpectres = new();
}

public sealed class Character : Component { }

public sealed class CharacterRecord { }

public sealed class ForeignKeyAttribute(Type type, string field) : Attribute { }

public sealed class CharacterStableKeyResolver
{
    public string GetStableKey(Character character) => "character:" + character.gameObject.name;
}
