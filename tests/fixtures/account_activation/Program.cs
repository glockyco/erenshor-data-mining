using System.Text.Json;
using SQLite;
using UnityEngine;

internal static class Program
{
    private static GameObject Host(
        string identity,
        ActivationTargetResolver targets,
        bool active = true,
        GameObject? parent = null
    )
    {
        var host = new GameObject
        {
            name = "Spawn Point",
            FixtureObjectKey = "object:reliquary:" + identity,
            activeSelf = active,
            Parent = parent,
        };
        targets.Subjects.Add(
            host,
            new[]
            {
                new ActivationTarget
                {
                    Kind = "object",
                    Key = host.FixtureObjectKey,
                    Scene = "Reliquary",
                    ObjectName = host.name,
                    IsEnabled = host.activeInHierarchy,
                },
            }
        );
        return host;
    }

    private static SpawnPoint Spawn(GameObject host, string key, ActivationTargetResolver targets)
    {
        var spawn = host.Add(new SpawnPoint());
        targets.SpawnKeys.Add(spawn, key);
        targets.Subjects[host] = targets
            .Subjects[host]
            .Append(
                new ActivationTarget
                {
                    Kind = "spawn_point",
                    Key = key,
                    Scene = host.scene.name,
                    ObjectName = host.name,
                    IsEnabled = spawn.isActiveAndEnabled,
                }
            )
            .ToArray();
        return spawn;
    }

    private static object Rows(SQLiteConnection db) =>
        new
        {
            sources = db.Rows<ScriptedActivatorRecord>(),
            references = db.Rows<ScriptedActivatorReferenceRecord>(),
            targets = db.Rows<ScriptedActivatorTargetRecord>(),
            operations = db.Operations,
        };

    private static object AccountBindings(DynamicSpawnCatalog catalog, string activity)
    {
        var db = new SQLiteConnection();
        var targets = new ActivationTargetResolver();
        var listener = new ScriptedActivatorListener(
            db,
            new CharacterStableKeyResolver(),
            targets,
            catalog
        );
        var input = new List<object>();
        var expected = new List<SpawnPoint>();
        for (int index = 0; index < 2; index++)
        {
            // Identical names cannot identify the binding. The hosts have distinct registered identities.
            var parent =
                activity == "inactive_parent" ? new GameObject { activeSelf = false } : null;
            var host = Host("host[" + index + "]", targets, activity != "inactive_self", parent);
            host.transform.position = new Vector3
            {
                x = 11 + index,
                y = 22,
                z = 33,
            };
            var key = "spawn:reliquary:fixture-host-" + index;
            var spawn = Spawn(host, key, targets);
            spawn.canSpawn = index == 0;
            // An enabled SpawnPoint remains enabled even when its sibling suppressor is disabled.
            var suppressor = host.Add(new ReliqDisableFiendSpawn { enabled = index == 0 });
            listener.OnAssetFound(suppressor);
            expected.Add(spawn);
            input.Add(
                new
                {
                    objectKey = host.FixtureObjectKey,
                    spawnKey = key,
                    componentEnabled = suppressor.enabled,
                    effectiveActive = suppressor.isActiveAndEnabled,
                    hostActiveSelf = host.activeSelf,
                    hostActiveInHierarchy = host.activeInHierarchy,
                    spawnComponentEnabled = spawn.enabled,
                    spawnCanSpawn = spawn.canSpawn,
                    spawnEffectiveActive = spawn.isActiveAndEnabled,
                }
            );
        }
        var writesBeforeFinish = db.Operations.Count;
        listener.OnScanFinished();
        return new
        {
            activity,
            input,
            writesBeforeFinish,
            rows = Rows(db),
            exactHostSpawnRequests = targets.SpawnRequests.SequenceEqual(expected),
            resolveRequests = targets.ResolveRequests.Select(request => new
            {
                objectKey = request.Host.FixtureObjectKey,
                enabling = request.Enabling,
            }),
        };
    }

    private static object AllCatalogRules(DynamicSpawnCatalog catalog)
    {
        var db = new SQLiteConnection();
        var targets = new ActivationTargetResolver();
        var listener = new ScriptedActivatorListener(
            db,
            new CharacterStableKeyResolver(),
            targets,
            catalog
        );
        var target = Host("configured-target[0]", targets);
        var spawn = Spawn(target, "spawn:fixture:configured-target", targets);
        var character = target.Add(new Character { FixtureKey = "character:fixture:ward" });
        var line = target.Add(new Zoneline { FixtureKey = "zoneline:fixture:configured-target" });
        targets.Subjects[target] = targets
            .Subjects[target]
            .Append(
                new ActivationTarget
                {
                    Kind = "zone_line",
                    Key = line.FixtureKey,
                    Scene = target.scene.name,
                    ObjectName = target.name,
                    IsEnabled = line.isActiveAndEnabled,
                }
            )
            .ToArray();
        var item = new Item { FixtureKey = "item:fixture:required" };
        var quest = new Quest { FixtureKey = "quest:fixture:required" };
        var controllers = new Dictionary<Type, MonoBehaviour>();
        foreach (var entry in catalog.Activations)
        {
            var type =
                typeof(Program).Assembly.GetType(entry.Script)
                ?? throw new InvalidOperationException(
                    "Missing typed fixture controller: " + entry.Script
                );
            var host = Host(entry.Script + "[0]", targets);
            if (
                type == typeof(NPCShoutListener)
                || type == typeof(ReliquaryFiend)
                || type == typeof(ShiveringPhantomWardListener)
            )
                host.Add(new Character { FixtureKey = "character:fixture:" + entry.Script });
            if (type == typeof(ReliqDisableFiendSpawn))
                Spawn(host, "spawn:fixture:catalog-account-host", targets);
            var controller = host.Add((MonoBehaviour)Activator.CreateInstance(type));
            controllers[type] = controller;
            foreach (var name in entry.Fields)
            {
                var field =
                    type.GetField(name)
                    ?? throw new InvalidOperationException(
                        "Missing typed fixture field: " + entry.Script + "." + name
                    );
                object value =
                    field.FieldType == typeof(GameObject) ? target
                    : field.FieldType == typeof(SpawnPoint) ? spawn
                    : field.FieldType == typeof(Zoneline) ? line
                    : field.FieldType == typeof(Character) ? character
                    : field.FieldType == typeof(Item) ? item
                    : field.FieldType == typeof(Quest) ? quest
                    : field.FieldType == typeof(bool) ? false
                    : field.FieldType == typeof(string) ? "38656873"
                    // A controller reference names a controller that an earlier catalog entry placed.
                    : controllers.TryGetValue(field.FieldType, out var referenced) ? referenced
                    : field.FieldType == typeof(List<GameObject>)
                        ? new List<GameObject> { target, target }
                    : field.FieldType == typeof(List<SpawnPoint>) ? new List<SpawnPoint> { spawn }
                    : throw new InvalidOperationException(
                        "Unexpected typed fixture field: " + field
                    );
                field.SetValue(controller, value);
            }
            if (controller is AstraListener astra)
                astra.Dragon = target;
            if (controller is StowawayPortal)
            {
                spawn.NPCSpecificObject = host;
                spawn.CommonSpawns.Add(target);
                target.Add(new SkeletonCheckin());
                host.scene.Roots.Add(target);
                var keeper = Host("keeper-prefab", targets);
                keeper.Add(new Character { FixtureKey = "character:fixture:keeper" });
                keeper.Add(new SkeletonCheckin { Keeper = true });
                spawn.RareSpawns.Add(keeper);
                var unrelated = Host("unrelated-checkin-spawn", targets);
                var unrelatedSpawn = Spawn(unrelated, "spawn:fixture:unrelated-checkin", targets);
                unrelatedSpawn.CommonSpawns.Add(target);
                host.scene.Roots.Add(unrelated);
            }
            listener.OnAssetFound(controller);
        }
        listener.OnScanFinished();
        return new
        {
            catalog = catalog.Activations,
            catalogEntryCount = catalog.Entries.Count,
            rows = Rows(db),
        };
    }

    private static object MissingHostSpawn(DynamicSpawnCatalog catalog)
    {
        var db = new SQLiteConnection();
        var targets = new ActivationTargetResolver();
        var listener = new ScriptedActivatorListener(
            db,
            new CharacterStableKeyResolver(),
            targets,
            catalog
        );
        var unrelatedHost = Host("unrelated[0]", targets);
        Spawn(unrelatedHost, "spawn:fixture:not-the-host", targets);
        var host = Host("missing[0]", targets);
        var suppressor = host.Add(new ReliqDisableFiendSpawn { enabled = false });
        string error = null;
        try
        {
            listener.OnAssetFound(suppressor);
        }
        catch (InvalidOperationException exception)
        {
            error = exception.Message;
        }
        // A failed scan must not call OnScanFinished. The test checks failure occurs during discovery.
        return new
        {
            error,
            rows = Rows(db),
            spawnRequests = targets.SpawnRequests.Count,
            sourceKey = host.FixtureObjectKey + ":script:ReliqDisableFiendSpawn:0",
        };
    }

    private static object PortalStartup(
        DynamicSpawnCatalog catalog,
        string activity,
        string missing = null
    )
    {
        var db = new SQLiteConnection();
        var targets = new ActivationTargetResolver();
        var listener = new ScriptedActivatorListener(
            db,
            new CharacterStableKeyResolver(),
            targets,
            catalog
        );
        var parent = activity == "inactive_parent" ? new GameObject { activeSelf = false } : null;
        var portal = Host("return-portal", targets, activity != "inactive_self", parent);
        var line = portal.Add(new Zoneline { FixtureKey = "zoneline:fixture:stored-return" });
        targets.Subjects[portal] = targets
            .Subjects[portal]
            .Append(
                new ActivationTarget
                {
                    Kind = "zone_line",
                    Key = line.FixtureKey,
                    Scene = portal.scene.name,
                    ObjectName = portal.name,
                    IsEnabled = line.isActiveAndEnabled,
                }
            )
            .ToArray();
        var host = Host("return-controller", targets);
        var controller = host.Add(
            new ReliqPortalListener
            {
                ReliqZL = missing == "line" ? null : line,
                ReliqPort = missing == "portal" ? null : portal,
            }
        );
        string error = null;
        try
        {
            listener.OnAssetFound(controller);
            listener.OnScanFinished();
        }
        catch (InvalidOperationException exception)
        {
            error = exception.Message;
        }
        return new
        {
            activity,
            missing,
            error,
            portalActiveSelf = portal.activeSelf,
            portalActiveInHierarchy = portal.activeInHierarchy,
            lineKey = line.FixtureKey,
            portalKey = portal.FixtureObjectKey,
            rows = Rows(db),
        };
    }

    public static void Main(string[] args)
    {
        if (args.Length != 1)
            throw new ArgumentException("Pass the production dynamic-spawn catalog path");
        var catalog = DynamicSpawnCatalog.Load(args[0]);
        Console.WriteLine(
            JsonSerializer.Serialize(
                new
                {
                    allRules = AllCatalogRules(catalog),
                    accounts = new[] { "active", "inactive_self", "inactive_parent" }.Select(
                        activity => AccountBindings(catalog, activity)
                    ),
                    missing = MissingHostSpawn(catalog),
                    portals = new[] { "active", "inactive_self", "inactive_parent" }.Select(
                        activity => PortalStartup(catalog, activity)
                    ),
                    missingPortalBindings = new[] { "line", "portal" }.Select(missing =>
                        PortalStartup(catalog, "inactive_self", missing)
                    ),
                    unknownCandidates = UnknownCandidateCases.Capture(catalog),
                }
            )
        );
    }
}
