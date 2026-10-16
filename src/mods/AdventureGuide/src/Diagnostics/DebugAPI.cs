using System.Globalization;
using System.Text;
using AdventureGuide.Data;
using AdventureGuide.Navigation;
using AdventureGuide.State;
using AdventureGuide.UI;

namespace AdventureGuide.Diagnostics;

/// <summary>
/// Static API for runtime inspection via HotRepl.
/// All methods return human-readable strings for eval output.
///
/// Static fields are set by Plugin on startup and cleared on destroy.
/// HotRepl's evaluator auto-resets on ScriptEngine hot reload (F6),
/// resolving types from the newest assembly, so these fields always
/// point to the live Plugin's state.
/// </summary>
public static class DebugAPI
{
    internal static GuideData? Data { get; set; }
    internal static QuestStateTracker? State { get; set; }
    internal static FilterState? Filter { get; set; }
    internal static NavigationController? Nav { get; set; }
    internal static EntityRegistry? Entities { get; set; }
    internal static GroundPathRenderer? GroundPath { get; set; }
    internal static WorldMarkerSystem? Markers { get; set; }

    /// <summary>Dump current mod state: zone, active/completed counts, filter state.</summary>
    public static string DumpState()
    {
        if (State == null)
            return "Not initialized";

        return $"Zone: {State.CurrentZone}\n"
            + $"Active quests: {State.ActiveQuests.Count}\n"
            + $"Completed quests: {State.CompletedQuests.Count}\n"
            + $"Selected: {State.SelectedQuestKey ?? "(none)"}\n"
            + $"Filter: {Filter?.FilterMode}\n"
            + $"Sort: {Filter?.SortMode}\n"
            + $"Search: '{Filter?.SearchText ?? ""}'\n"
            + $"Zone filter: {Filter?.ZoneFilter ?? "(all)"}";
    }

    /// <summary>Dump navigation target, requirements, waypoint, distance, and ground path.</summary>
    public static string DumpNav()
    {
        if (Nav == null)
            return "Not initialized";

        var sb = new StringBuilder();
        if (Nav.OriginQuest is QuestEntry origin && Nav.OriginStep is QuestStep originStep)
            sb.AppendLine($"Origin: {origin.RuntimeKey} step {originStep.Order}");

        if (Nav.Requirements is RequirementResolution requirements)
        {
            sb.AppendLine($"Requirements: canNavigate={requirements.CanNavigate}");
            sb.AppendLine(
                $"  Endpoint: {requirements.Quest.RuntimeKey} step {requirements.Step.Order}"
            );
            for (int i = 0; i < requirements.Chain.Count; i++)
            {
                var link = requirements.Chain[i];
                sb.AppendLine($"  {i + 1}. {link.Label}");
                if (link.Atom is GateAtom atom)
                    sb.AppendLine(
                        $"     Atom: {atom.Kind} {atom.Ref} slot={atom.Slot ?? "(none)"}"
                    );
                foreach (string alternative in link.Alternatives)
                    sb.AppendLine($"     Alternative: {alternative}");
            }
            foreach (var advisory in requirements.Advisories)
                sb.AppendLine($"  Advisory: {advisory.Kind} {advisory.Ref}");
            if (!string.IsNullOrEmpty(requirements.Message))
                sb.AppendLine($"  Message: {requirements.Message}");
        }
        else
            sb.AppendLine("Requirements: (none)");

        if (Nav.ChosenEntryLine is ZoneLineEntry entry)
        {
            int entryIndex = -1;
            if (Data != null)
                for (int i = 0; i < Data.ZoneLines.Count; i++)
                    if (ReferenceEquals(Data.ZoneLines[i], entry))
                    {
                        entryIndex = i;
                        break;
                    }
            sb.AppendLine($"EntryLine: {entryIndex} {entry.Scene}|{entry.DestinationZoneKey}");
            sb.AppendLine($"  Position: ({entry.X}, {entry.Y}, {entry.Z})");
            sb.AppendLine($"  Condition: {entry.Condition?.ToString() ?? "(none)"}");
        }
        else
            sb.AppendLine("EntryLine: (any)");

        if (Nav.Target is not NavigationTarget t)
        {
            sb.AppendLine("No active navigation target");
            return sb.ToString();
        }

        sb.AppendLine($"Target: {t.DisplayName}");
        sb.AppendLine($"  Kind: {t.TargetKind}");
        sb.AppendLine($"  Scene: {t.Scene}");
        sb.AppendLine($"  Position: {t.Position}");
        sb.AppendLine($"  SourceId: {t.SourceId ?? "(none)"}");
        sb.AppendLine($"  Quest: {t.QuestKey} step {t.StepOrder}");
        sb.AppendLine($"  Origin: {t.OriginQuestKey} step {t.OriginStepOrder}");

        var currentZone = State?.CurrentZone ?? "";
        sb.AppendLine($"  CrossZone: {t.IsCrossZone(currentZone)}");
        sb.AppendLine($"  Distance: {Nav.Distance:F1}");

        if (Nav.ZoneLineWaypoint != null)
        {
            var zl = Nav.ZoneLineWaypoint;
            sb.AppendLine($"ZoneLineWaypoint: {zl.DisplayName}");
            sb.AppendLine($"  Scene: {zl.Scene}");
            sb.AppendLine($"  Position: {zl.Position}");
        }
        else
        {
            sb.AppendLine("ZoneLineWaypoint: (none)");
        }

        if (GroundPath != null)
            sb.AppendLine($"GroundPath: enabled={GroundPath.Enabled}");

        sb.AppendLine($"ManualOverride: {Nav.IsManualSourceOverride}");

        return sb.ToString();
    }

    /// <summary>Dump entity registry state for a display name, or summary if null.</summary>
    public static string DumpEntities(string? displayName = null)
    {
        if (Entities == null)
            return "Not initialized";

        if (displayName != null)
        {
            string key = displayName.StartsWith(
                "character:",
                System.StringComparison.OrdinalIgnoreCase
            )
                ? displayName
                : CharacterStableKey.FromObjectName(displayName);
            int count = Entities.CountAlive(key);
            return $"{key}: {count} alive";
        }

        return "Pass a character name or stable key: DumpEntities(\"NPC Name\")";
    }

    /// <summary>Dump the current world markers: type, name, sub-text, and spawn point.</summary>
    public static string DumpMarkers() => Markers?.Describe() ?? "Not initialized";

    /// <summary>
    /// Dump conditions for a character stable key, spawn:scene:x:y:z, or
    /// scene|destination (destination scene, stable key, or display name).
    /// </summary>
    public static string DumpGate(string subject)
    {
        if (Data == null || State == null)
            return "Not initialized";

        subject = subject.Trim();
        var lines = new StringBuilder();
        if (Data.CharacterSpawns.TryGetValue(subject, out var characterSpawns))
        {
            lines.AppendLine($"Character: {subject}");
            lines.AppendLine($"Available: {State.Gates.IsCharacterAvailable(subject)}");
            foreach (var spawn in characterSpawns)
            {
                lines.AppendLine($"Spawn: {SpawnGateKey(spawn)}");
                AppendGate(lines, spawn.Condition);
            }
            return lines.ToString();
        }

        if (TryParseSpawnGateKey(subject, out var scene, out var x, out var y, out var z))
        {
            foreach (var character in Data.CharacterSpawns)
            {
                foreach (var spawn in character.Value)
                {
                    if (
                        !string.Equals(spawn.Scene, scene, StringComparison.OrdinalIgnoreCase)
                        || Math.Abs(spawn.X - x) > 0.005f
                        || Math.Abs(spawn.Y - y) > 0.005f
                        || Math.Abs(spawn.Z - z) > 0.005f
                    )
                        continue;
                    lines.AppendLine($"Spawn: {SpawnGateKey(spawn)}");
                    lines.AppendLine($"Character: {character.Key}");
                    lines.AppendLine($"Available: {State.Gates.IsSpawnAvailable(spawn)}");
                    AppendGate(lines, spawn.Condition);
                }
            }
            return lines.Length > 0 ? lines.ToString() : $"Spawn '{subject}' not found";
        }

        int separator = subject.IndexOf('|');
        if (separator > 0 && separator < subject.Length - 1)
        {
            scene = subject.Substring(0, separator).Trim();
            string destination = subject.Substring(separator + 1).Trim();
            string? destinationKey = Data.ZoneLookup.TryGetValue(destination, out var zone)
                ? zone.StableKey
                : null;
            foreach (var line in Data.ZoneLines)
            {
                if (
                    !string.Equals(line.Scene, scene, StringComparison.OrdinalIgnoreCase)
                    || !(
                        string.Equals(
                            line.DestinationZoneKey,
                            destinationKey ?? destination,
                            StringComparison.OrdinalIgnoreCase
                        )
                        || string.Equals(
                            line.DestinationDisplay,
                            destination,
                            StringComparison.OrdinalIgnoreCase
                        )
                    )
                )
                    continue;
                lines.AppendLine(
                    $"Zone line: {line.Scene}|{line.DestinationZoneKey} ({line.DestinationDisplay})"
                );
                lines.AppendLine(
                    FormattableString.Invariant(
                        $"Position: {line.X:0.##}, {line.Y:0.##}, {line.Z:0.##}"
                    )
                );
                AppendGate(lines, line.Condition);
            }
            return lines.Length > 0 ? lines.ToString() : $"Zone line '{subject}' not found";
        }

        return $"Gate subject '{subject}' not found. Use a character stable key, "
            + "spawn:scene:x:y:z, or scene|destination.";
    }

    private static void AppendGate(StringBuilder lines, int? condition)
    {
        var gates = State!.Gates;
        lines.AppendLine(
            $"  Condition: {condition?.ToString(CultureInfo.InvariantCulture) ?? "(none)"}, available={gates.IsAvailable(condition)}"
        );
        if (!condition.HasValue)
        {
            lines.AppendLine("  Ungated");
            return;
        }
        if (condition.Value < 0 || condition.Value >= Data!.Conditions.Count)
        {
            lines.AppendLine("  Condition index is unresolved");
            return;
        }

        var groups = Data.Conditions[condition.Value];
        lines.AppendLine($"  Groups: {groups.Count} (any group, all atoms)");
        for (int i = 0; i < groups.Count; i++)
        {
            var group = groups[i];
            bool held = true;
            foreach (var atom in group)
                held &= gates.Holds(atom);
            lines.AppendLine($"  Group {i}: held={held}");
            foreach (var atom in group)
            {
                lines.AppendLine(
                    $"    {atom.Kind} ref={atom.Ref} slot={atom.Slot ?? "(none)"} held={gates.Holds(atom)}"
                );
                lines.AppendLine($"      {gates.Describe(atom)}");
                if (atom.Kind is GateAtomKind.KeyHeld or GateAtomKind.ItemHeld)
                {
                    Data.GateItems.TryGetValue(atom.Ref, out var item);
                    string? gameId = item?.GameId ?? atom.GameId;
                    string onKeyring = string.IsNullOrEmpty(gameId)
                        ? "(unresolved)"
                        : gates.Facts.IsOnKeyring(gameId).ToString();
                    lines.AppendLine(
                        $"      Item: {item?.Name ?? atom.Ref}, game_id={gameId ?? "(unresolved)"}"
                    );
                    lines.AppendLine(
                        $"      Inventory: {gates.Facts.ItemCount(atom.Ref)}, keyring={onKeyring}"
                    );
                }
                else if (atom.Kind == GateAtomKind.RoomFurnished && atom.Slot != null)
                    lines.AppendLine(
                        $"      Room {atom.Slot}: {gates.Facts.FurnitureIn(atom.Slot) ?? "(empty)"}"
                    );
            }
        }
    }

    private static string SpawnGateKey(AdventureGuide.Data.SpawnPoint spawn) =>
        FormattableString.Invariant(
            $"spawn:{spawn.Scene}:{spawn.X:0.##}:{spawn.Y:0.##}:{spawn.Z:0.##}"
        );

    private static bool TryParseSpawnGateKey(
        string subject,
        out string scene,
        out float x,
        out float y,
        out float z
    )
    {
        scene = "";
        x = y = z = 0;
        var parts = subject.Split(':');
        if (
            parts.Length != 5
            || !string.Equals(parts[0], "spawn", StringComparison.OrdinalIgnoreCase)
            || !float.TryParse(parts[2], NumberStyles.Float, CultureInfo.InvariantCulture, out x)
            || !float.TryParse(parts[3], NumberStyles.Float, CultureInfo.InvariantCulture, out y)
            || !float.TryParse(parts[4], NumberStyles.Float, CultureInfo.InvariantCulture, out z)
        )
            return false;
        scene = parts[1];
        return true;
    }

    /// <summary>Dump full details for a specific quest by DB name or display name.</summary>
    public static string DumpQuest(string name)
    {
        if (Data == null)
            return "Not initialized";

        var q = FindQuest(name);
        if (q == null)
            return $"Quest '{name}' not found (searched DB name and display name)";

        var lines = new System.Text.StringBuilder();
        lines.AppendLine($"DBName: {q.DBName}");
        lines.AppendLine($"Name: {q.DisplayName}");
        lines.AppendLine($"Type: {q.QuestType}");
        lines.AppendLine($"Zone: {q.ZoneContext}");
        lines.AppendLine($"Level: {q.LevelEstimate?.Recommended}");
        lines.AppendLine($"RuntimeKey: {q.RuntimeKey}");
        lines.AppendLine($"Active: {State?.IsActive(q)}");
        lines.AppendLine($"Completed: {State?.IsCompleted(q)}");
        if (q.IsGuideOnly)
        {
            lines.AppendLine($"WorkflowStage: {State?.Workflows.GetStage(q)}");
            lines.AppendLine($"WorkflowGeneration: {State?.Workflows.GetGeneration(q)}");
        }

        if (q.Steps != null)
        {
            lines.AppendLine($"Steps ({q.Steps.Count}):");
            foreach (var s in q.Steps)
                lines.AppendLine(
                    $"  {s.Order}. [{s.Action}] {s.Description} (target_key={s.TargetKey})"
                );
        }

        if (q.Rewards != null)
            lines.AppendLine(
                $"Rewards: {q.Rewards.XP} XP, {q.Rewards.Gold} Gold, {q.Rewards.ItemName}"
            );

        return lines.ToString();
    }

    /// <summary>Dump all quests for the current zone.</summary>
    public static string DumpZoneQuests()
    {
        if (Data == null || State == null)
            return "Not initialized";

        var zone = State.CurrentZone;
        var lines = new System.Text.StringBuilder();
        lines.AppendLine($"Quests in zone '{zone}':");

        foreach (var q in Data.All)
        {
            if (q.ZoneContext == null)
                continue;
            if (!q.ZoneContext.Equals(zone, System.StringComparison.OrdinalIgnoreCase))
                continue;

            var status = State.GetStatus(q) switch
            {
                QuestRuntimeStatus.Completed => "done",
                QuestRuntimeStatus.Active => "active",
                QuestRuntimeStatus.ImplicitlyActive => "completable here",
                _ => "available",
            };
            lines.AppendLine($"  [{status}] {q.DisplayName} ({q.DBName})");
        }

        return lines.ToString();
    }

    /// <summary>
    /// Remove a quest from the player's active and completed lists so it
    /// can be accepted again. Accepts DB name or display name. Syncs the
    /// mod's cached state after modification.
    /// </summary>
    public static string ResetQuest(string name)
    {
        if (Data == null || State == null)
            return "Not initialized";

        var q = FindQuest(name);
        if (q == null)
            return $"Quest '{name}' not found";

        if (q.IsGuideOnly)
            return $"'{q.DisplayName}' is guide-only; its cycle resets from observed game evidence.";

        bool wasActive = GameData.HasQuest.Remove(q.DBName);
        bool wasCompleted = GameData.CompletedQuests.Remove(q.DBName);

        State.SyncFromGameData();
        Nav?.OnGameStateChanged(State.CurrentZone);

        string prev =
            wasActive ? "active"
            : wasCompleted ? "completed"
            : "not in quest log";
        return $"Reset '{q.DisplayName}' (was {prev})";
    }

    /// <summary>Test zone graph routing between two scenes.</summary>
    public static string TestRoute(string fromScene, string toScene)
    {
        if (Nav == null)
            return "Not initialized";
        var graphField = typeof(NavigationController).GetField(
            "_zoneGraph",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance
        );
        var graph = graphField?.GetValue(Nav) as ZoneGraph;
        if (graph == null)
            return "ZoneGraph not found";
        var route = graph.FindRoute(fromScene, toScene);
        if (route == null)
            return $"No route from {fromScene} to {toScene}";
        return $"NextHop={route.NextHopZoneKey} IsLocked={route.IsLocked} Path={string.Join(" -> ", route.Path)}";
    }

    private static QuestEntry? FindQuest(string name)
    {
        if (Data == null)
            return null;
        var q = Data.GetByRuntimeKey(name) ?? Data.GetByStableKey(name);
        if (q != null)
            return q;
        foreach (var entry in Data.All)
        {
            if (string.Equals(entry.DisplayName, name, System.StringComparison.OrdinalIgnoreCase))
                return entry;
        }
        return null;
    }
}
