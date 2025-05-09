using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using UnityEditor;
using UnityEngine;
using SQLite;

public class AssetScannerExporterWindow : EditorWindow
{
    private const string EditorPrefsKeyPath = "Erenshor_AssetScannerExporter_OutputPath";
    private const string DefaultFilename = "Erenshor.sqlite";

    private string _outputPath;
    private SQLiteConnection _db;
    
    private bool _isScanning;
    private bool _cancelRequested;
    private string _status = "Idle";
    private double _elapsedSeconds;
    private Stopwatch _stopwatch;
    private AssetScanProgress _progress = new();
    private AssetScanner _activeScanner;

    private AscensionListener _ascensionListener;
    private BookListener _bookListener;
    private CharacterListener _characterListener;
    private ClassListener _classListener;
    private ItemListener _itemListener;
    private LootTableListener _lootTableListener;
    private MiningNodeListener _miningNodeListener;
    private NpcDialogListener _npcDialogListener;
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
    private bool _exportNpcDialogs = true;
    private bool _exportQuests = true;
    private bool _exportSkills = true;
    private bool _exportSpells = true;
    private bool _exportSpawnPoints = true;
    private bool _exportWorldFactions = true;
    private bool _exportZoneAtlasEntries = true;

    [MenuItem("Tools/Export Game Data")] 
    public static void ShowWindow()
    {
        var window = GetWindow<AssetScannerExporterWindow>("Asset Scanner Exporter");
        window.minSize = new Vector2(500, 300);
        window.Show();
    }

    private void OnEnable()
    {
        _outputPath = EditorPrefs.GetString(EditorPrefsKeyPath, Path.Combine(Application.dataPath, DefaultFilename));
        _db = new SQLiteConnection(_outputPath);
        
        _ascensionListener = new AscensionListener(_db);
        _bookListener = new BookListener(_db);
        _characterListener = new CharacterListener(_db);
        _classListener = new ClassListener(_db);
        _itemListener = new ItemListener(_db);
        _lootTableListener = new LootTableListener(_db);
        _miningNodeListener = new MiningNodeListener(_db);
        _npcDialogListener = new NpcDialogListener(_db);
        _questListener = new QuestListener(_db);
        _skillListener = new SkillListener(_db);
        _spellListener = new SpellListener(_db);
        _spawnPointListener = new SpawnPointListener(_db);
        _worldFactionListener = new WorldFactionListener(_db);
        _zoneAtlasEntryListener = new ZoneAtlasEntryListener(_db);
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
                    EditorPrefs.SetString(EditorPrefsKeyPath, _outputPath);
                }
            } catch { /* Ignore errors, keep old path */ }
        }
        if (GUILayout.Button("Browse...", GUILayout.Width(80)))
        {
            string directory = string.IsNullOrEmpty(_outputPath) ? Application.dataPath + "/.." : Path.GetDirectoryName(_outputPath);
            string filename = string.IsNullOrEmpty(_outputPath) ? DefaultFilename : Path.GetFileName(_outputPath);
            if (!string.IsNullOrEmpty(directory) && !Directory.Exists(directory))
                directory = Application.dataPath + "/..";
            string chosenPath = EditorUtility.SaveFilePanel("Select Database Output Path", directory, filename, "sqlite");
            if (!string.IsNullOrEmpty(chosenPath))
            {
                _outputPath = chosenPath;
                EditorPrefs.SetString(EditorPrefsKeyPath, _outputPath);
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
        _exportNpcDialogs = EditorGUILayout.ToggleLeft("NPC Dialogs", _exportNpcDialogs);
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
        _exportNpcDialogs = value;
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
        
        _activeScanner = new AssetScanner();
        if (_exportAscensions) _activeScanner.RegisterScriptableObjectListener(_ascensionListener);
        if (_exportBooks) _activeScanner.RegisterScriptableObjectListener(_bookListener);
        if (_exportCharacters) _activeScanner.RegisterComponentListener(_characterListener);
        if (_exportClasses) _activeScanner.RegisterScriptableObjectListener(_classListener);
        if (_exportItems) _activeScanner.RegisterScriptableObjectListener(_itemListener);
        if (_exportLootTables) _activeScanner.RegisterComponentListener(_lootTableListener);
        if (_exportMiningNodes) _activeScanner.RegisterComponentListener(_miningNodeListener);
        if (_exportNpcDialogs) _activeScanner.RegisterComponentListener(_npcDialogListener);
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
        bool anyStepSelected = _exportAscensions || _exportBooks || _exportCharacters || _exportClasses || _exportWorldFactions || _exportItems || _exportLootTables || _exportMiningNodes || _exportNpcDialogs || _exportQuests || _exportSkills || _exportSpells || _exportSpawnPoints || _exportZoneAtlasEntries;
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
