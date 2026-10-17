#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using SQLite;
using UnityEditor;
using UnityEngine;

public sealed class CharacterDamageReleaseListener : IAssetScanListener<MonoBehaviour>
{
    private readonly SQLiteConnection _db;
    private readonly CharacterStableKeyResolver _characters;
    private readonly ActivationTargetResolver _targets;
    private readonly Dictionary<string, CharacterDamageReleaseRecord> _records = new();

    public CharacterDamageReleaseListener(
        SQLiteConnection db,
        CharacterStableKeyResolver characters,
        ActivationTargetResolver targets
    )
    {
        _db = db;
        _characters = characters;
        _targets = targets;
        RequireField<NPCInvuln>("Protector", typeof(GameObject));
        RequireField<ActivateInWeather>("ActiveNoRain", typeof(List<GameObject>));
        RequireField<ActivateInWeather>("ActiveInRain", typeof(List<GameObject>));
        RequireField<SpawnPoint>("Protector", typeof(GameObject));
        RequireField<SpawnPoint>("CommonSpawns", typeof(List<GameObject>));
        RequireField<SpawnPoint>("RareSpawns", typeof(List<GameObject>));
        RequireField<SpawnPoint>("RareNPCChance", typeof(int));
        RequireField<QuestManager>("NPCQuests", typeof(List<Quest>));
        RequireField<Quest>("DropInvulnOnHolder", typeof(bool));
        RequireField<Quest>("RequiredItems", typeof(List<Item>));
        RequireField<NPCPhaseShiftManager>("Phases", typeof(List<NPCPhaseShift>));
        RequireField<NPCPhaseShiftManager>("ShiftAtLife", typeof(int));
        RequireField<NPCPhaseShift>("DelayBeforeCombat", typeof(float));
        RequireField<FernallaFightEvent>("thisSpawnPoint", typeof(SpawnPoint));
        RequireField<PhantomFightEvent>("WardSpawnPoints", typeof(List<Transform>));
        RequireField<PhantomFightEvent>("WardsToSpawn", typeof(GameObject));
        RequireField<PhantomFightEvent>("LivingWards", typeof(List<Character>));
        RequireField<AEEvent>("isLifetap", typeof(bool));
        RequireField<NPC>("NeverAggro", typeof(bool));
        RequireField<SprinklesEvent>("SprinklesSpawn", typeof(SpawnPoint));
    }

    public void OnAssetFound(MonoBehaviour asset)
    {
        switch (asset)
        {
            case Character character:
                ExportTradeReleases(character);
                break;
            case SpawnPoint spawn when Placed(spawn):
                foreach (var candidate in SpawnCharacters(spawn))
                foreach (var controller in candidate.GetComponents<NPCInvuln>())
                    ExportProtector(controller, candidate, spawn);
                break;
            case NPCInvuln protector:
                var host = RequireHost(protector);
                // A prefab's null is not the runtime value. SpawnPoint can replace
                // it before Start, so only a real binding proves this branch.
                if (Placed(protector))
                    ExportProtector(protector, host, null);
                else
                    Add(
                        host,
                        "npc_protector_null",
                        Source(protector),
                        false,
                        protector.enabled,
                        ("state", "runtime_binding_required")
                    );
                break;
            case NPCPhaseShiftManager phase:
                ExportHealthPhase(phase);
                break;
            case FernallaFightEvent fight when Placed(fight):
                ExportSpawnHealthPhase(fight);
                break;
            case PhantomFightEvent wards:
                ExportCombatWards(wards);
                break;
            case SprinklesEvent emptyWards when Placed(emptyWards):
                ExportEmptyWards(emptyWards);
                break;
        }
    }

    public void OnScanFinished()
    {
        _db.CreateTable<CharacterDamageReleaseRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<CharacterDamageReleaseRecord>();
            _db.InsertAll(_records.Values);
        });
        _records.Clear();
    }

    // code-fact: combat.release.trade_holder
    // code-fact: combat.release.trade_items
    // code-fact: combat.release.trade_flag
    // code-fact: combat.release.trade_component
    // code-fact: combat.release.trade_required_items
    // code-fact: combat.release.trade_available
    private void ExportTradeReleases(Character character)
    {
        var manager = character.GetComponent<QuestManager>();
        if (manager == null || manager.NPCQuests == null)
            return;
        foreach (var quest in manager.NPCQuests)
        {
            if (quest == null || !quest.DropInvulnOnHolder)
                continue;
            // TradeWindow reads the component directly, even when disabled.
            // Keep the actual resource variant, not the shared quest DBName.
            Add(
                character,
                "trade_turn_in",
                Source(manager) + ":quest:" + Uri.EscapeDataString(quest.name),
                quest.RequiredItems != null,
                true,
                ("quest_variant", quest.name)
            );
        }
    }

    // code-fact: combat.release.protector_host
    // code-fact: combat.release.protector_update
    // code-fact: combat.release.spawn_protector
    private void ExportProtector(NPCInvuln controller, Character host, SpawnPoint? spawn)
    {
        var source = Source(controller);
        // Placement activation is a separate gate. A host's component can run
        // after its quest or event enables the character.
        var enabled = controller.enabled;
        var protector = controller.Protector;
        var conditions = new List<(string kind, string? key)>();
        if (spawn != null)
        {
            var spawnKey = _targets.GetStableKey(spawn);
            source += ":spawn:" + spawnKey;
            conditions.Add(("spawn_point", spawnKey));
            enabled &= spawn.enabled;
            // SpawnPoint only overwrites a non-null binding.
            if (spawn.Protector != null)
                protector = spawn.Protector;
        }
        if (protector == null)
        {
            conditions.Add(("state", "protector_null"));
            Add(host, "npc_protector_null", source, true, enabled, conditions.ToArray());
            return;
        }
        var protectorKey = ObjectReference(protector);
        conditions.Add(("object", protectorKey));
        Add(
            host,
            "npc_protector_inactive",
            source,
            !protector.activeSelf,
            enabled,
            conditions.ToArray()
        );
        if (!Placed(protector.transform))
            return;
        // Inspect while the scene is loaded. AssetScanner replaces scenes before
        // OnScanFinished, so retaining Unity references would lose bindings.
        foreach (var root in protector.scene.GetRootGameObjects())
        foreach (var weather in root.GetComponentsInChildren<ActivateInWeather>(true))
            ExportWeather(host, weather, protector, source, enabled, conditions);
    }

    // code-fact: combat.release.weather_order
    private void ExportWeather(
        Character host,
        ActivateInWeather weather,
        GameObject protector,
        string source,
        bool enabled,
        List<(string kind, string? key)> conditions
    )
    {
        bool dryList = weather.ActiveNoRain != null && weather.ActiveNoRain.Contains(protector);
        bool rainList = weather.ActiveInRain != null && weather.ActiveInRain.Contains(protector);
        bool validLists = weather.ActiveNoRain != null && weather.ActiveInRain != null;
        if (!dryList && !rainList)
            return;
        var weatherSource = Source(weather);
        var evidence = new List<(string kind, string? key)>(conditions)
        {
            ("controller", weatherSource),
        };
        evidence.Add(("state", "raining"));
        // ActiveInRain runs last in both branches. Disabling an ancestor does
        // not change Protector.activeSelf and therefore is not a release.
        Add(
            host,
            "npc_protector_weather",
            source + ":weather:" + weatherSource + ":rain",
            validLists && dryList && !rainList,
            enabled && weather.isActiveAndEnabled,
            evidence.ToArray()
        );
        evidence[evidence.Count - 1] = ("state", "dry_after_rain");
        Add(
            host,
            "npc_protector_weather",
            source + ":weather:" + weatherSource + ":dry",
            validLists && rainList,
            enabled && weather.isActiveAndEnabled,
            evidence.ToArray()
        );
    }

    // code-fact: combat.release.health_phase_update
    // code-fact: combat.release.health_phase_start
    // code-fact: combat.release.health_phase_host
    private void ExportHealthPhase(NPCPhaseShiftManager controller)
    {
        var host = RequireHost(controller);
        bool phase =
            host.GetComponent<Stats>() != null
            && host.GetComponent<NPC>() != null
            && host.GetComponent<Animator>() != null
            && controller.Phases != null
            && controller.Phases.Count > 0
            && controller.Phases[0] != null
            && controller.Phases[0].DelayBeforeCombat > 0f;
        Add(
            host,
            "health_phase_timer",
            Source(controller),
            phase && controller.ShiftAtLife > 0 && !host.Invulnerable,
            controller.enabled,
            ("state", "requires_prior_damage")
        );
    }

    // code-fact: combat.release.spawn_health_binding
    // code-fact: combat.release.spawn_health_gate
    // code-fact: combat.release.spawn_health_timer
    // code-fact: combat.release.spawn_health_phase
    // code-fact: combat.release.spawn_health_start
    private void ExportSpawnHealthPhase(FernallaFightEvent controller)
    {
        var spawn =
            controller.thisSpawnPoint != null
                ? controller.thisSpawnPoint
                : controller.GetComponent<SpawnPoint>();
        if (spawn == null)
            throw new InvalidOperationException(
                "Health phase controller has no runtime SpawnPoint binding"
            );
        foreach (var host in SpawnCharacters(spawn))
            Add(
                host,
                "spawn_health_phase_timer",
                Source(controller),
                !host.Invulnerable,
                BoundControllerEnabled(controller, spawn),
                ("spawn_point", _targets.GetStableKey(spawn)),
                ("state", "requires_prior_damage")
            );
    }

    // code-fact: combat.release.combat_ward_gate
    // code-fact: combat.release.combat_ward_spawn
    // code-fact: combat.release.combat_ward_death
    // code-fact: combat.release.combat_ward_host
    private void ExportCombatWards(PhantomFightEvent controller)
    {
        var host = RequireHost(controller);
        var ward =
            controller.WardsToSpawn != null
                ? controller.WardsToSpawn.GetComponent<Character>()
                : null;
        bool feasible =
            ward != null
            && CanEngage(host)
            && controller.LivingWards != null
            && controller.WardSpawnPoints != null
            && controller.WardSpawnPoints.Count > 0;
        if (feasible)
            foreach (var position in controller.WardSpawnPoints)
                feasible &= position != null;
        var source = Source(controller);
        Add(
            host,
            "combat_ward_cycle",
            source,
            feasible,
            controller.enabled,
            ("character", ward != null ? _characters.GetStableKey(ward) : null),
            ("state", "aggro_then_ward_death")
        );
        if (ward != null)
            Add(
                ward,
                "combat_ward_cycle",
                source + ":spawned_ward",
                feasible,
                controller.enabled,
                ("character", _characters.GetStableKey(host)),
                ("state", "random_ward_unprotected")
            );
    }

    // code-fact: combat.release.empty_ward_binding
    // code-fact: combat.release.empty_ward_gate
    // code-fact: combat.release.empty_ward_initial
    private void ExportEmptyWards(SprinklesEvent controller)
    {
        var spawn = controller.SprinklesSpawn;
        if (spawn == null)
            return;
        foreach (var host in SpawnCharacters(spawn))
        {
            bool lifetap = false;
            bool offensive = false;
            foreach (var effect in host.GetComponents<AEEvent>())
            {
                lifetap |= effect.isLifetap;
                offensive |= !effect.isLifetap;
            }
            Add(
                host,
                "combat_empty_wards",
                Source(controller),
                lifetap && offensive && CanEngage(host),
                BoundControllerEnabled(controller, spawn),
                ("spawn_point", _targets.GetStableKey(spawn)),
                ("state", "aggro_empty_ward_list")
            );
        }
    }

    private void Add(
        Character host,
        string mechanism,
        string source,
        bool canRelease,
        bool enabled,
        params (string kind, string? key)[] conditions
    )
    {
        var characterKey = _characters.GetStableKey(host);
        foreach (var condition in conditions)
        {
            var key =
                characterKey
                + ":damage_release:"
                + mechanism
                + ":"
                + source
                + ":"
                + condition.kind
                + ":"
                + Uri.EscapeDataString(condition.key ?? "");
            _records[key] = new CharacterDamageReleaseRecord
            {
                RuleKey = key,
                CharacterStableKey = characterKey,
                Mechanism = mechanism,
                SourceStableKey = source,
                ConditionKind = condition.kind,
                ConditionStableKey = condition.key,
                CanRelease = canRelease,
                ControllerEnabled = enabled,
            };
        }
    }

    private string Source(MonoBehaviour controller)
    {
        var host = controller.GetComponent<Character>();
        var key =
            Placed(controller) ? ActivationTargetResolver.ObjectKey(controller.gameObject)
            : host != null ? _characters.GetStableKey(host)
            : throw new InvalidOperationException(
                "Prefab release controller requires a host Character"
            );
        return key
            + ":script:"
            + controller.GetType().Name
            + ":"
            + Array
                .IndexOf(controller.GetComponents(controller.GetType()), controller)
                .ToString(CultureInfo.InvariantCulture);
    }

    private string ObjectReference(GameObject target)
    {
        if (Placed(target.transform))
            return ActivationTargetResolver.ObjectKey(target);
        var path = AssetDatabase.GetAssetPath(target);
        if (string.IsNullOrEmpty(path))
            throw new InvalidOperationException("Protector has no scene or asset identity");
        if (
            !AssetDatabase.TryGetGUIDAndLocalFileIdentifier(
                target,
                out string guid,
                out long localId
            )
        )
            throw new InvalidOperationException("Protector asset has no stable identity");
        return "asset:" + guid + ":" + localId.ToString(CultureInfo.InvariantCulture);
    }

    private static bool Placed(Component component) =>
        component.gameObject.scene.IsValid()
        && !PrefabUtility.IsPartOfPrefabAsset(component.gameObject);

    private static bool BoundControllerEnabled(MonoBehaviour controller, SpawnPoint spawn) =>
        spawn.enabled
        && controller.enabled
        // A controller on the spawn object shares its activation gate. A
        // separate manager needs its own runnable proof.
        && (controller.gameObject == spawn.gameObject || controller.gameObject.activeInHierarchy);

    // code-fact: combat.release.engagement_gate
    private static bool CanEngage(Character character)
    {
        var npc = character.GetComponent<NPC>();
        return npc != null && npc.enabled && !npc.NeverAggro;
    }

    private static Character RequireHost(MonoBehaviour controller) =>
        controller.GetComponent<Character>()
        ?? throw new InvalidOperationException(
            $"{controller.GetType().Name} requires a host Character"
        );

    // code-fact: combat.release.spawn_selection
    private static IEnumerable<Character> SpawnCharacters(SpawnPoint spawn)
    {
        var seen = new HashSet<int>();
        if (
            spawn.CommonSpawns != null
            && (
                spawn.RareSpawns == null || spawn.RareSpawns.Count == 0 || spawn.RareNPCChance < 100
            )
        )
            foreach (var obj in spawn.CommonSpawns)
                if (
                    obj != null
                    && obj.TryGetComponent<Character>(out var character)
                    && seen.Add(character.GetInstanceID())
                )
                    yield return character;
        if (spawn.RareSpawns != null && spawn.RareNPCChance > 0)
            foreach (var obj in spawn.RareSpawns)
                if (
                    obj != null
                    && obj.TryGetComponent<Character>(out var character)
                    && seen.Add(character.GetInstanceID())
                )
                    yield return character;
    }

    private static void RequireField<T>(string name, Type expected)
    {
        var field = typeof(T).GetField(name, BindingFlags.Instance | BindingFlags.Public);
        if (field == null || field.FieldType != expected)
            throw new InvalidOperationException(
                $"Missing or retyped damage release field: {typeof(T).Name}.{name}"
            );
    }
}
