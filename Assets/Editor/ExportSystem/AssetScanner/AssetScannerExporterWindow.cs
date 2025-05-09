using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using UnityEditor;
using UnityEngine;
using SQLite;
using Debug = UnityEngine.Debug;

public class AssetScannerExporterWindow : EditorWindow
{
    private const string EDITOR_PREFS_KEY_PATH = "Erenshor_AssetScannerExporter_OutputPath";
    private const string DEFAULT_FILENAME = "Erenshor.sqlite";

    private string _outputPath;
    private bool _isScanning;
    private bool _cancelRequested;
    private string _status = "Idle";
    private double _elapsedSeconds;
    private Stopwatch _stopwatch;
    private AssetScanProgress _progress = new AssetScanProgress();
    private AssetScanner _activeScanner;

    private AscensionListener _ascensionListener;
    private BookCollector _bookCollector;
    private CharacterListener _characterListener;
    private ClassListener _classListener;
    private ItemListener _itemListener;
    private LootTableListener _lootTableListener;
    private MiningNodeListener _miningNodeListener;
    private NPCDialogListener _npcDialogListener;
    private QuestListener _questListener;
    private SkillListener _skillListener;
    private SpellListener _spellListener;
    private SpawnPointListener _spawnPointListener;
    private WorldFactionListener _worldFactionListener;
    private ZoneAtlasEntryListener _zoneAtlasEntryListener;

    private bool _selectAllSteps = true;
    private bool _exportAscensions = true;
    private bool _exportBooks = true;
    private bool _exportCharacters = true;
    private bool _exportClasses = true;
    private bool _exportItems = true;
    private bool _exportLootTables = true;
    private bool _exportMiningNodes = true;
    private bool _exportNPCDialogs = true;
    private bool _exportQuests = true;
    private bool _exportSkills = true;
    private bool _exportSpells = true;
    private bool _exportSpawnPoints = true;
    private bool _exportWorldFactions = true;
    private bool _exportZoneAtlasEntries = true;

    [MenuItem("Tools/Asset Scanner/Export Assets")] 
    public static void ShowWindow()
    {
        var window = GetWindow<AssetScannerExporterWindow>("Asset Scanner Exporter");
        window.minSize = new Vector2(500, 300);
        window.Show();
    }

    private void OnEnable()
    {
        _outputPath = EditorPrefs.GetString(EDITOR_PREFS_KEY_PATH, Path.Combine(Application.dataPath, DEFAULT_FILENAME));
        _ascensionListener = new AscensionListener();
        _bookCollector = new BookCollector();
        _characterListener = new CharacterListener();
        _classListener = new ClassListener();
        _itemListener = new ItemListener();
        _lootTableListener = new LootTableListener();
        _miningNodeListener = new MiningNodeListener();
        _npcDialogListener = new NPCDialogListener();
        _questListener = new QuestListener();
        _skillListener = new SkillListener();
        _spellListener = new SpellListener();
        _spawnPointListener = new SpawnPointListener();
        _worldFactionListener = new WorldFactionListener();
        _zoneAtlasEntryListener = new ZoneAtlasEntryListener();
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
                    EditorPrefs.SetString(EDITOR_PREFS_KEY_PATH, _outputPath);
                }
            } catch { /* Ignore errors, keep old path */ }
        }
        if (GUILayout.Button("Browse...", GUILayout.Width(80)))
        {
            string directory = string.IsNullOrEmpty(_outputPath) ? Application.dataPath + "/.." : Path.GetDirectoryName(_outputPath);
            string filename = string.IsNullOrEmpty(_outputPath) ? DEFAULT_FILENAME : Path.GetFileName(_outputPath);
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
                directory = Application.dataPath + "/..";
            string chosenPath = EditorUtility.SaveFilePanel("Select Database Output Path", directory, filename, "sqlite");
            if (!string.IsNullOrEmpty(chosenPath))
            {
                _outputPath = chosenPath;
                EditorPrefs.SetString(EDITOR_PREFS_KEY_PATH, _outputPath);
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
        _exportAscensions = EditorGUILayout.ToggleLeft("Ascensions", _exportAscensions);
        _exportBooks = EditorGUILayout.ToggleLeft("Books", _exportBooks);
        _exportCharacters = EditorGUILayout.ToggleLeft("Characters", _exportCharacters);
        _exportClasses = EditorGUILayout.ToggleLeft("Classes", _exportClasses);
        _exportItems = EditorGUILayout.ToggleLeft("Items", _exportItems);
        _exportLootTables = EditorGUILayout.ToggleLeft("Loot Drops", _exportLootTables);
        _exportMiningNodes = EditorGUILayout.ToggleLeft("Mining Nodes", _exportMiningNodes);
        _exportNPCDialogs = EditorGUILayout.ToggleLeft("NPC Dialogs", _exportNPCDialogs);
        _exportQuests = EditorGUILayout.ToggleLeft("Quests", _exportQuests);
        _exportSkills = EditorGUILayout.ToggleLeft("Skills", _exportSkills);
        _exportSpells = EditorGUILayout.ToggleLeft("Spells", _exportSpells);
        _exportSpawnPoints = EditorGUILayout.ToggleLeft("Spawn Points", _exportSpawnPoints);
        _exportWorldFactions = EditorGUILayout.ToggleLeft("World Factions", _exportWorldFactions);
        _exportZoneAtlasEntries = EditorGUILayout.ToggleLeft("Zone Atlas Entries", _exportZoneAtlasEntries);
        EditorGUI.EndDisabledGroup();
    }

    private void SetAllStepToggles(bool value)
    {
        _exportAscensions = value;
        _exportBooks = value;
        _exportCharacters = value;
        _exportClasses = value;
        _exportItems = value;
        _exportLootTables = value;
        _exportMiningNodes = value;
        _exportNPCDialogs = value;
        _exportQuests = value;
        _exportSkills = value;
        _exportSpells = value;
        _exportSpawnPoints = value;
        _exportWorldFactions = value;
        _exportZoneAtlasEntries = value;
    }

    private void StartScanAndExport()
    {
        _status = "Running";
        _elapsedSeconds = 0;
        _isScanning = true;
        _cancelRequested = false;
        _progress = new AssetScanProgress();
        // Reset only selected listeners
        if (_exportAscensions) _ascensionListener.Reset();
        if (_exportBooks) _bookCollector.Reset();
        if (_exportCharacters) _characterListener.Reset();
        if (_exportClasses) _classListener.Reset();
        if (_exportItems) _itemListener.Reset();
        if (_exportLootTables) _lootTableListener.Reset();
        if (_exportMiningNodes) _miningNodeListener.Reset();
        if (_exportNPCDialogs) _npcDialogListener.Reset();
        if (_exportQuests) _questListener.Reset();
        if (_exportSkills) _skillListener.Reset();
        if (_exportSpells) _spellListener.Reset();
        if (_exportSpawnPoints) _spawnPointListener.Reset();
        if (_exportWorldFactions) _worldFactionListener.Reset();
        if (_exportZoneAtlasEntries) _zoneAtlasEntryListener.Reset();
        // Create scanner and register only selected listeners
        _activeScanner = new AssetScanner();
        if (_exportAscensions) _activeScanner.RegisterScriptableObjectListener(_ascensionListener);
        if (_exportCharacters) _activeScanner.RegisterComponentListener(_characterListener);
        if (_exportClasses) _activeScanner.RegisterScriptableObjectListener(_classListener);
        if (_exportItems) _activeScanner.RegisterScriptableObjectListener(_itemListener);
        if (_exportLootTables) _activeScanner.RegisterComponentListener(_lootTableListener);
        if (_exportMiningNodes) _activeScanner.RegisterComponentListener(_miningNodeListener);
        if (_exportNPCDialogs) _activeScanner.RegisterComponentListener(_npcDialogListener);
        if (_exportQuests) _activeScanner.RegisterScriptableObjectListener(_questListener);
        if (_exportSkills) _activeScanner.RegisterScriptableObjectListener(_skillListener);
        if (_exportSpells) _activeScanner.RegisterScriptableObjectListener(_spellListener);
        if (_exportSpawnPoints) _activeScanner.RegisterComponentListener(_spawnPointListener);
        if (_exportWorldFactions) _activeScanner.RegisterScriptableObjectListener(_worldFactionListener);
        if (_exportZoneAtlasEntries) _activeScanner.RegisterScriptableObjectListener(_zoneAtlasEntryListener);
        _stopwatch = Stopwatch.StartNew();
        EditorCoroutineRunner.StartCoroutine(ScanAndExportCoroutine());
    }

    private IEnumerator ScanAndExportCoroutine()
    {
        if (_exportBooks) _bookCollector.Collect();
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
        _status = _cancelRequested ? "Cancelled" : "Exporting...";
        Repaint();
        if (!_cancelRequested)
        {
            var exportTask = Task.Run(() => ExportToDatabase(_outputPath));
            while (!exportTask.IsCompleted)
                yield return null;
            if (exportTask.Exception != null)
            {
                Debug.LogError($"Failed to export: {exportTask.Exception}");
                _status = "Failed: " + exportTask.Exception.Message;
            }
            else
            {
                _status = "Done";
            }
        }
        else
        {
            _status = "Cancelled";
        }
        Repaint();
    }

    private void ExportToDatabase(string dbPath)
    {
        using var db = new SQLiteConnection(dbPath);
        if (_exportAscensions) db.CreateTable<AscensionDBRecord>();
        if (_exportBooks) db.CreateTable<BookDBRecord>();
        if (_exportCharacters) db.CreateTable<CharacterDBRecord>();
        if (_exportClasses) db.CreateTable<ClassDBRecord>();
        if (_exportItems) db.CreateTable<ItemDBRecord>();
        if (_exportLootTables) db.CreateTable<LootTableDBRecord>();
        if (_exportMiningNodes) db.CreateTable<MiningNodeDBRecord>();
        if (_exportNPCDialogs) db.CreateTable<NPCDialogDBRecord>();
        if (_exportQuests) db.CreateTable<QuestDBRecord>();
        if (_exportSkills) db.CreateTable<SkillDBRecord>();
        if (_exportSpells) db.CreateTable<SpellDBRecord>();
        if (_exportSpawnPoints) db.CreateTable<SpawnPointDBRecord>();
        if (_exportWorldFactions) db.CreateTable<WorldFactionDBRecord>();
        if (_exportZoneAtlasEntries) db.CreateTable<ZoneAtlasEntryDBRecord>();
        db.RunInTransaction(() =>
        {
            if (_exportAscensions) { db.DeleteAll<AscensionDBRecord>(); db.InsertAll(_ascensionListener.Records); }
            if (_exportBooks) { db.DeleteAll<BookDBRecord>(); db.InsertAll(_bookCollector.Records); }
            if (_exportCharacters) { db.DeleteAll<CharacterDBRecord>(); db.InsertAll(_characterListener.Records); }
            if (_exportClasses) { db.DeleteAll<ClassDBRecord>(); db.InsertAll(_classListener.Records); }
            if (_exportItems) { db.DeleteAll<ItemDBRecord>(); db.InsertAll(_itemListener.Records); }
            if (_exportLootTables) { db.DeleteAll<LootTableDBRecord>(); db.InsertAll(_lootTableListener.Records); }
            if (_exportMiningNodes) { db.DeleteAll<MiningNodeDBRecord>(); db.InsertAll(_miningNodeListener.Records); }
            if (_exportNPCDialogs) { db.DeleteAll<NPCDialogDBRecord>(); db.InsertAll(_npcDialogListener.Records); }
            if (_exportQuests) { db.DeleteAll<QuestDBRecord>(); db.InsertAll(_questListener.Records); }
            if (_exportSkills) { db.DeleteAll<SkillDBRecord>(); db.InsertAll(_skillListener.Records); }
            if (_exportSpells) { db.DeleteAll<SpellDBRecord>(); db.InsertAll(_spellListener.Records); }
            if (_exportSpawnPoints) { db.DeleteAll<SpawnPointDBRecord>(); db.InsertAll(_spawnPointListener.Records); }
            if (_exportWorldFactions) { db.DeleteAll<WorldFactionDBRecord>(); db.InsertAll(_worldFactionListener.Records); }
            if (_exportZoneAtlasEntries) { db.DeleteAll<ZoneAtlasEntryDBRecord>(); db.InsertAll(_zoneAtlasEntryListener.Records); }
        });
    }

    private void DrawStatusAndActionsSection()
    {
        GUILayout.Label("Overall Status:", EditorStyles.boldLabel);
        EditorGUILayout.LabelField(_status);
        EditorGUILayout.Space();
        EditorGUILayout.BeginHorizontal();
        bool anyStepSelected = _exportAscensions || _exportBooks || _exportCharacters || _exportClasses || _exportWorldFactions || _exportItems || _exportLootTables || _exportMiningNodes || _exportNPCDialogs || _exportQuests || _exportSkills || _exportSpells || _exportSpawnPoints || _exportZoneAtlasEntries;
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
        bool fileExists = !_isScanning && !string.IsNullOrEmpty(_outputPath) && System.IO.File.Exists(_outputPath);
        EditorGUI.BeginDisabledGroup(!fileExists);
        if (GUILayout.Button("Open Output Folder"))
        {
            EditorUtility.RevealInFinder(_outputPath);
        }
        EditorGUI.EndDisabledGroup();
    }
}
