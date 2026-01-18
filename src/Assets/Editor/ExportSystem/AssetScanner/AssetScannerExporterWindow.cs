using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEngine;
using SQLite;

public class AssetScannerExporterWindow : EditorWindow
{
    private string _outputPath;
    private SQLiteConnection _db;

    private bool _isScanning;
    private bool _cancelRequested;
    private string _status = "Idle";
    private double _elapsedSeconds;
    private Stopwatch _stopwatch;
    private AssetScanProgress _progress = new();
    private AssetScanner _activeScanner;

    private bool _selectAllSteps = true;
    private bool _exportAchievementTriggers = true;
    private bool _exportAscensions = true;
    private bool _exportBooks = true;
    private bool _exportCharacters = true;
    private bool _exportClasses = true;
    private bool _exportDoors = true;
    private bool _exportForges = true;
    private bool _exportGuildTopics = true;
    private bool _exportItemBags = true;
    private bool _exportItems = true;
    private bool _exportLootTables = true;
    private bool _exportMiningNodes = true;
    private bool _exportQuests = true;
    private bool _exportSecretPassages = true;
    private bool _exportSkills = true;
    private bool _exportSpells = true;
    private bool _exportStances = true;
    private bool _exportSpawnPoints = true;
    private bool _exportTeleportLocs = true;
    private bool _exportTreasureHunting = true;
    private bool _exportTreasureLocs = true;
    private bool _exportWaters = true;
    private bool _exportWishingWells = true;
    private bool _exportWorldFactions = true;
    private bool _exportZoneAnnounces = true;
    private bool _exportZoneAtlasEntries = true;
    private bool _exportZoneLines = true;

    [MenuItem("Tools/Export Game Data")]
    public static void ShowWindow()
    {
        var window = GetWindow<AssetScannerExporterWindow>("Asset Scanner Exporter");
        window.minSize = new Vector2(500, 300);
        window.Show();
    }

    private void OnEnable()
    {
        _outputPath = Repository.GetDefaultDatabasePath();
    }

    private void OnDisable()
    {
        _cancelRequested = true;
    }

    private void OnGUI()
    {
        GUILayout.Label("Asset Scanner Exporter", EditorStyles.boldLabel);
        EditorGUILayout.Space();
        DrawConfigurationSection();
        DrawProgressSection();
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider);
        DrawStepSelectionSection();
        EditorGUILayout.Space();
        EditorGUILayout.LabelField("", GUI.skin.horizontalSlider);
        DrawStatusAndActionsSection();
    }

    private void DrawConfigurationSection()
    {
        GUILayout.Label("Output Database File", EditorStyles.boldLabel);
        EditorGUILayout.BeginHorizontal();
        string displayPath = _outputPath;
        string projectPath = Path.GetFullPath(Application.dataPath + "/../");
        if (!string.IsNullOrEmpty(_outputPath) && _outputPath.StartsWith(projectPath))
            displayPath = Path.GetRelativePath(projectPath, _outputPath);
        string newPath = EditorGUILayout.TextField(displayPath, GUILayout.ExpandWidth(true));
        if (newPath != displayPath)
        {
            try {
                string potentialFullPath = Path.IsPathRooted(newPath) ? Path.GetFullPath(newPath) : Path.GetFullPath(Path.Combine(projectPath, newPath));
                string directory = Path.GetDirectoryName(potentialFullPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    _outputPath = potentialFullPath;
                    EditorPrefs.SetString(Repository.EditorPrefsKey, _outputPath);
                }
            } catch (System.Exception ex) {
                UnityEngine.Debug.LogError($"[AssetScannerExporterWindow] Invalid output path: {newPath}. Error: {ex.Message}");
                EditorUtility.DisplayDialog("Invalid Path", $"The specified output path is invalid:\n\n{newPath}\n\nError: {ex.Message}", "OK");
            }
        }
        if (GUILayout.Button("Browse...", GUILayout.Width(80)))
        {
            string directory = string.IsNullOrEmpty(_outputPath) ? Application.dataPath + "/.." : Path.GetDirectoryName(_outputPath);
            string filename = string.IsNullOrEmpty(_outputPath) ? Repository.DefaultFilename : Path.GetFileName(_outputPath);
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
                directory = Application.dataPath + "/..";
            string chosenPath = EditorUtility.SaveFilePanel("Select Database Output Path", directory, filename, "sqlite");
            if (!string.IsNullOrEmpty(chosenPath))
            {
                _outputPath = chosenPath;
                EditorPrefs.SetString(Repository.EditorPrefsKey, _outputPath);
            }
        }
        EditorGUILayout.EndHorizontal();
    }

    private void DrawProgressSection()
    {
        if (!_isScanning) return;
        float progress = (_progress.Total > 0) ? (float)_progress.Current / _progress.Total : 0f;
        string label = $"{_progress.Phase ?? ""} ({_progress.Current}/{_progress.Total})";
        GUILayout.Space(10);
        EditorGUILayout.LabelField("Progress:", EditorStyles.boldLabel);
        Rect rect = GUILayoutUtility.GetRect(18, 18, "TextField");
        EditorGUI.ProgressBar(rect, progress, label);
        string timeStr = _elapsedSeconds > 0 ? TimeSpan.FromSeconds(_elapsedSeconds).ToString(@"hh\:mm\:ss") : "00:00:00";
        EditorGUILayout.LabelField($"Elapsed: {timeStr}", EditorStyles.miniLabel);
    }

    private void DrawStepSelectionSection()
    {
        GUILayout.Label("Export Steps", EditorStyles.boldLabel);
        EditorGUI.BeginChangeCheck();
        _selectAllSteps = EditorGUILayout.ToggleLeft(" Select / Deselect All", _selectAllSteps);
        if (EditorGUI.EndChangeCheck())
        {
            SetAllStepToggles(_selectAllSteps);
        }
        EditorGUI.BeginDisabledGroup(_selectAllSteps);
        _exportAchievementTriggers = EditorGUILayout.ToggleLeft("Achievement Triggers", _exportAchievementTriggers);
        _exportAscensions = EditorGUILayout.ToggleLeft("Ascensions", _exportAscensions);
        _exportBooks = EditorGUILayout.ToggleLeft("Books", _exportBooks);
        _exportCharacters = EditorGUILayout.ToggleLeft("Characters", _exportCharacters);
        _exportClasses = EditorGUILayout.ToggleLeft("Classes", _exportClasses);
        _exportDoors = EditorGUILayout.ToggleLeft("Doors", _exportDoors);
        _exportForges = EditorGUILayout.ToggleLeft("Forges", _exportForges);
        _exportGuildTopics = EditorGUILayout.ToggleLeft("Guild Topics", _exportGuildTopics);
        _exportItemBags = EditorGUILayout.ToggleLeft("Item Bags", _exportItemBags);
        _exportItems = EditorGUILayout.ToggleLeft("Items", _exportItems);
        _exportLootTables = EditorGUILayout.ToggleLeft("Loot Drops", _exportLootTables);
        _exportMiningNodes = EditorGUILayout.ToggleLeft("Mining Nodes", _exportMiningNodes);
        _exportQuests = EditorGUILayout.ToggleLeft("Quests", _exportQuests);
        _exportSecretPassages = EditorGUILayout.ToggleLeft("Secret Passages", _exportSecretPassages);
        _exportSkills = EditorGUILayout.ToggleLeft("Skills", _exportSkills);
        _exportSpells = EditorGUILayout.ToggleLeft("Spells", _exportSpells);
        _exportStances = EditorGUILayout.ToggleLeft("Stances", _exportStances);
        _exportSpawnPoints = EditorGUILayout.ToggleLeft("Spawn Points", _exportSpawnPoints);
        _exportTeleportLocs = EditorGUILayout.ToggleLeft("Teleport Locations", _exportTeleportLocs);
        _exportTreasureHunting = EditorGUILayout.ToggleLeft("Treasure Hunting", _exportTreasureHunting);
        _exportTreasureLocs = EditorGUILayout.ToggleLeft("Treasure Locations", _exportTreasureLocs);
        _exportWaters = EditorGUILayout.ToggleLeft("Waters", _exportWaters);
        _exportWishingWells = EditorGUILayout.ToggleLeft("Wishing Wells", _exportWishingWells);
        _exportWorldFactions = EditorGUILayout.ToggleLeft("World Factions", _exportWorldFactions);
        _exportZoneAnnounces = EditorGUILayout.ToggleLeft("Zones", _exportZoneAnnounces);
        _exportZoneAtlasEntries = EditorGUILayout.ToggleLeft("Zone Atlas Entries", _exportZoneAtlasEntries);
        _exportZoneLines = EditorGUILayout.ToggleLeft("Zone Lines", _exportZoneLines);
        EditorGUI.EndDisabledGroup();
    }

    private void SetAllStepToggles(bool value)
    {
        _exportAchievementTriggers = value;
        _exportAscensions = value;
        _exportBooks = value;
        _exportCharacters = value;
        _exportClasses = value;
        _exportDoors = value;
        _exportForges = value;
        _exportGuildTopics = value;
        _exportItemBags = value;
        _exportItems = value;
        _exportLootTables = value;
        _exportMiningNodes = value;
        _exportQuests = value;
        _exportSecretPassages = value;
        _exportSkills = value;
        _exportSpells = value;
        _exportStances = value;
        _exportSpawnPoints = value;
        _exportTeleportLocs = value;
        _exportTreasureHunting = value;
        _exportTreasureLocs = value;
        _exportWaters = value;
        _exportWishingWells = value;
        _exportWorldFactions = value;
        _exportZoneAnnounces = value;
        _exportZoneAtlasEntries = value;
        _exportZoneLines = value;
    }

    private void StartScanAndExport()
    {
        _status = "Running";
        _elapsedSeconds = 0;
        _isScanning = true;
        _cancelRequested = false;
        _progress = new AssetScanProgress();

        _activeScanner = new AssetScanner();

        _db = new SQLiteConnection(_outputPath);

        if (_exportTeleportLocs) _activeScanner.RegisterNullListener(new TeleportLocListener(_db));

        if (_exportSecretPassages) _activeScanner.RegisterGameObjectListener(new SecretPassageListener(_db));
        if (_exportWishingWells) _activeScanner.RegisterGameObjectListener(new WishingWellListener(_db));

        if (_exportAscensions) _activeScanner.RegisterScriptableObjectListener(new AscensionListener(_db));
        if (_exportBooks) _activeScanner.RegisterScriptableObjectListener(new BookListener(_db));
        if (_exportClasses) _activeScanner.RegisterScriptableObjectListener(new ClassListener(_db));
        // DISABLED: GuildTopic and Stance types only exist in playtest variant
        // if (_exportGuildTopics) _activeScanner.RegisterScriptableObjectListener(new GuildTopicListener(_db));
        if (_exportQuests) _activeScanner.RegisterScriptableObjectListener(new QuestListener(_db));
        if (_exportSkills) _activeScanner.RegisterScriptableObjectListener(new SkillListener(_db));
        if (_exportSpells) _activeScanner.RegisterScriptableObjectListener(new SpellListener(_db));
        // if (_exportStances) _activeScanner.RegisterScriptableObjectListener(new StanceListener(_db));
        if (_exportWorldFactions) _activeScanner.RegisterScriptableObjectListener(new WorldFactionListener(_db));
        if (_exportZoneAtlasEntries) _activeScanner.RegisterScriptableObjectListener(new ZoneAtlasEntryListener(_db));

        // Item wikiStrings depend on spells for proc data, so we need to register items later.
        if (_exportItems) _activeScanner.RegisterScriptableObjectListener(new ItemListener(_db));

        if (_exportAchievementTriggers) _activeScanner.RegisterComponentListener(new AchievementTriggerListener(_db));
        if (_exportDoors) _activeScanner.RegisterComponentListener(new DoorListener(_db));
        if (_exportForges) _activeScanner.RegisterComponentListener(new ForgeListener(_db));
        if (_exportItemBags) _activeScanner.RegisterComponentListener(new ItemBagListener(_db));
        if (_exportLootTables) _activeScanner.RegisterComponentListener(new LootTableListener(_db));
        if (_exportLootTables) _activeScanner.RegisterComponentListener(new MiscListener(_db));
        if (_exportMiningNodes) _activeScanner.RegisterComponentListener(new MiningNodeListener(_db));
        if (_exportSpawnPoints) _activeScanner.RegisterComponentListener(new SpawnPointListener(_db));
        if (_exportTreasureHunting) _activeScanner.RegisterComponentListener(new TreasureHuntingListener(_db));
        if (_exportTreasureLocs) _activeScanner.RegisterComponentListener(new TreasureLocListener(_db));
        if (_exportWaters) _activeScanner.RegisterComponentListener(new WaterListener(_db));
        if (_exportZoneAnnounces) _activeScanner.RegisterComponentListener(new ZoneAnnounceListener(_db));
        if (_exportZoneLines) _activeScanner.RegisterComponentListener(new ZoneLineListener(_db));

        // Characters.IsUnique depends on spawn point data, so we need to register characters later.
        if (_exportCharacters) _activeScanner.RegisterComponentListener(new CharacterListener(_db));

        _stopwatch = Stopwatch.StartNew();
        EditorCoroutineRunner.StartCoroutine(ScanAndExportCoroutine());
    }

    private IEnumerator ScanAndExportCoroutine()
    {
        var scanCoroutine = _activeScanner.ScanAllAssetsCoroutine(
            () => _cancelRequested,
            progress => { _progress = progress; Repaint(); });
        while (scanCoroutine.MoveNext())
        {
            _elapsedSeconds = _stopwatch.Elapsed.TotalSeconds;
            Repaint();
            yield return scanCoroutine.Current;
        }
        _elapsedSeconds = _stopwatch.Elapsed.TotalSeconds;
        _isScanning = false;
        _status = _cancelRequested ? "Cancelled" : "Done";
        Repaint();
    }

    private void DrawStatusAndActionsSection()
    {
        GUILayout.Label("Overall Status:", EditorStyles.boldLabel);
        EditorGUILayout.LabelField(_status);
        EditorGUILayout.Space();
        EditorGUILayout.BeginHorizontal();
        bool anyStepSelected =
            _exportAchievementTriggers ||
            _exportAscensions ||
            _exportBooks ||
            _exportCharacters ||
            _exportClasses ||
            _exportDoors ||
            _exportForges ||
            _exportGuildTopics ||
            _exportWorldFactions ||
            _exportItemBags ||
            _exportItems ||
            _exportLootTables ||
            _exportMiningNodes ||
            _exportQuests ||
            _exportSecretPassages ||
            _exportSkills ||
            _exportSpells ||
            _exportStances ||
            _exportSpawnPoints ||
            _exportTeleportLocs ||
            _exportTreasureHunting ||
            _exportTreasureLocs ||
            _exportWaters ||
            _exportWishingWells ||
            _exportZoneAnnounces ||
            _exportZoneAtlasEntries ||
            _exportZoneLines;
        EditorGUI.BeginDisabledGroup(_isScanning || !anyStepSelected || string.IsNullOrEmpty(_outputPath));
        if (GUILayout.Button("Export Selected Steps", GUILayout.Height(30)))
        {
            StartScanAndExport();
        }
        EditorGUI.EndDisabledGroup();
        EditorGUI.BeginDisabledGroup(!_isScanning);
        if (GUILayout.Button("Cancel Export", GUILayout.Height(30)))
        {
            _cancelRequested = true;
        }
        EditorGUI.EndDisabledGroup();
        EditorGUILayout.EndHorizontal();
        EditorGUILayout.Space();
        bool fileExists = !_isScanning && !string.IsNullOrEmpty(_outputPath) && File.Exists(_outputPath);
        EditorGUI.BeginDisabledGroup(!fileExists);
        if (GUILayout.Button("Open Output Folder"))
        {
            EditorUtility.RevealInFinder(_outputPath);
        }
        EditorGUI.EndDisabledGroup();
    }
}
