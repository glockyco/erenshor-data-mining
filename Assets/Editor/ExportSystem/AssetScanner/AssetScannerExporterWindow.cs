using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using Database;
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

    private AscensionScanListener _ascensionListener;
    private BookExportCollector _bookCollector;
    private CharacterScanListener _characterListener;
    private ClassScanListener _classListener;
    private FactionScanListener _factionListener;
    private ItemScanListener _itemListener;
    private LootDropScanListener _lootDropListener;
    private MiningNodeScanListener _miningNodeListener;
    private NPCDialogScanListener _npcDialogListener;
    private QuestScanListener _questListener;
    private SkillScanListener _skillListener;
    private SpellScanListener _spellListener;
    private SpawnPointScanListener _spawnPointListener;
    private ZoneAtlasEntryScanListener _zoneAtlasEntryListener;

    private bool _selectAllSteps = true;
    private bool _exportAscensions = true;
    private bool _exportBooks = true;
    private bool _exportCharacters = true;
    private bool _exportClasses = true;
    private bool _exportFactions = true;
    private bool _exportItems = true;
    private bool _exportLootDrops = true;
    private bool _exportMiningNodes = true;
    private bool _exportNPCDialogs = true;
    private bool _exportQuests = true;
    private bool _exportSkills = true;
    private bool _exportSpells = true;
    private bool _exportSpawnPoints = true;
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
        _outputPath = EditorPrefs.GetString(EDITOR_PREFS_KEY_PATH, GetDefaultPath());
        _ascensionListener = new AscensionScanListener();
        _bookCollector = new BookExportCollector();
        _characterListener = new CharacterScanListener();
        _classListener = new ClassScanListener();
        _factionListener = new FactionScanListener();
        _itemListener = new ItemScanListener();
        _lootDropListener = new LootDropScanListener();
        _miningNodeListener = new MiningNodeScanListener();
        _npcDialogListener = new NPCDialogScanListener();
        _questListener = new QuestScanListener();
        _skillListener = new SkillScanListener();
        _spellListener = new SpellScanListener();
        _spawnPointListener = new SpawnPointScanListener();
        _zoneAtlasEntryListener = new ZoneAtlasEntryScanListener();
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
        _exportFactions = EditorGUILayout.ToggleLeft("Factions", _exportFactions);
        _exportItems = EditorGUILayout.ToggleLeft("Items", _exportItems);
        _exportLootDrops = EditorGUILayout.ToggleLeft("Loot Drops", _exportLootDrops);
        _exportMiningNodes = EditorGUILayout.ToggleLeft("Mining Nodes", _exportMiningNodes);
        _exportNPCDialogs = EditorGUILayout.ToggleLeft("NPC Dialogs", _exportNPCDialogs);
        _exportQuests = EditorGUILayout.ToggleLeft("Quests", _exportQuests);
        _exportSkills = EditorGUILayout.ToggleLeft("Skills", _exportSkills);
        _exportSpells = EditorGUILayout.ToggleLeft("Spells", _exportSpells);
        _exportSpawnPoints = EditorGUILayout.ToggleLeft("Spawn Points", _exportSpawnPoints);
        _exportZoneAtlasEntries = EditorGUILayout.ToggleLeft("Zone Atlas Entries", _exportZoneAtlasEntries);
        EditorGUI.EndDisabledGroup();
    }

    private void SetAllStepToggles(bool value)
    {
        _exportAscensions = value;
        _exportBooks = value;
        _exportCharacters = value;
        _exportClasses = value;
        _exportFactions = value;
        _exportItems = value;
        _exportLootDrops = value;
        _exportMiningNodes = value;
        _exportNPCDialogs = value;
        _exportQuests = value;
        _exportSkills = value;
        _exportSpells = value;
        _exportSpawnPoints = value;
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
        if (_exportFactions) _factionListener.Reset();
        if (_exportItems) _itemListener.Reset();
        if (_exportLootDrops) _lootDropListener.Reset();
        if (_exportMiningNodes) _miningNodeListener.Reset();
        if (_exportNPCDialogs) _npcDialogListener.Reset();
        if (_exportQuests) _questListener.Reset();
        if (_exportSkills) _skillListener.Reset();
        if (_exportSpells) _spellListener.Reset();
        if (_exportSpawnPoints) _spawnPointListener.Reset();
        if (_exportZoneAtlasEntries) _zoneAtlasEntryListener.Reset();
        // Create scanner and register only selected listeners
        _activeScanner = new AssetScanner();
        if (_exportAscensions) _activeScanner.RegisterScriptableObjectListener(_ascensionListener);
        if (_exportCharacters) _activeScanner.RegisterComponentListener(_characterListener);
        if (_exportClasses) _activeScanner.RegisterScriptableObjectListener(_classListener);
        if (_exportFactions) _activeScanner.RegisterScriptableObjectListener(_factionListener);
        if (_exportItems) _activeScanner.RegisterScriptableObjectListener(_itemListener);
        if (_exportLootDrops) _activeScanner.RegisterComponentListener(_lootDropListener);
        if (_exportMiningNodes) _activeScanner.RegisterComponentListener(_miningNodeListener);
        if (_exportNPCDialogs) _activeScanner.RegisterComponentListener(_npcDialogListener);
        if (_exportQuests) _activeScanner.RegisterScriptableObjectListener(_questListener);
        if (_exportSkills) _activeScanner.RegisterScriptableObjectListener(_skillListener);
        if (_exportSpells) _activeScanner.RegisterScriptableObjectListener(_spellListener);
        if (_exportSpawnPoints) _activeScanner.RegisterComponentListener(_spawnPointListener);
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
        if (_exportFactions) db.CreateTable<FactionDBRecord>();
        if (_exportItems) db.CreateTable<ItemDBRecord>();
        if (_exportLootDrops) db.CreateTable<LootDropDBRecord>();
        if (_exportMiningNodes) db.CreateTable<MiningNodeDBRecord>();
        if (_exportNPCDialogs) db.CreateTable<NPCDialogDBRecord>();
        if (_exportQuests) db.CreateTable<QuestDBRecord>();
        if (_exportSkills) db.CreateTable<SkillDBRecord>();
        if (_exportSpells) db.CreateTable<SpellDBRecord>();
        if (_exportSpawnPoints) db.CreateTable<SpawnPointDBRecord>();
        if (_exportZoneAtlasEntries) db.CreateTable<ZoneAtlasEntryDBRecord>();
        db.RunInTransaction(() =>
        {
            if (_exportAscensions) { db.DeleteAll<AscensionDBRecord>(); db.InsertAll(_ascensionListener.Records); }
            if (_exportBooks) { db.DeleteAll<BookDBRecord>(); db.InsertAll(_bookCollector.Records); }
            if (_exportCharacters) { db.DeleteAll<CharacterDBRecord>(); db.InsertAll(_characterListener.Records); }
            if (_exportClasses) { db.DeleteAll<ClassDBRecord>(); db.InsertAll(_classListener.Records); }
            if (_exportFactions) { db.DeleteAll<FactionDBRecord>(); db.InsertAll(_factionListener.Records); }
            if (_exportItems) { db.DeleteAll<ItemDBRecord>(); db.InsertAll(_itemListener.Records); }
            if (_exportLootDrops) { db.DeleteAll<LootDropDBRecord>(); db.InsertAll(_lootDropListener.Records); }
            if (_exportMiningNodes) { db.DeleteAll<MiningNodeDBRecord>(); db.InsertAll(_miningNodeListener.Records); }
            if (_exportNPCDialogs) { db.DeleteAll<NPCDialogDBRecord>(); db.InsertAll(_npcDialogListener.Records); }
            if (_exportQuests) { db.DeleteAll<QuestDBRecord>(); db.InsertAll(_questListener.Records); }
            if (_exportSkills) { db.DeleteAll<SkillDBRecord>(); db.InsertAll(_skillListener.Records); }
            if (_exportSpells) { db.DeleteAll<SpellDBRecord>(); db.InsertAll(_spellListener.Records); }
            if (_exportSpawnPoints) { db.DeleteAll<SpawnPointDBRecord>(); db.InsertAll(_spawnPointListener.Records); }
            if (_exportZoneAtlasEntries) { db.DeleteAll<ZoneAtlasEntryDBRecord>(); db.InsertAll(_zoneAtlasEntryListener.Records); }
        });
    }

    private void DrawStatusAndActionsSection()
    {
        GUILayout.Label("Overall Status:", EditorStyles.boldLabel);
        EditorGUILayout.LabelField(_status);
        EditorGUILayout.Space();
        EditorGUILayout.BeginHorizontal();
        bool anyStepSelected = _exportAscensions || _exportBooks || _exportCharacters || _exportClasses || _exportFactions || _exportItems || _exportLootDrops || _exportMiningNodes || _exportNPCDialogs || _exportQuests || _exportSkills || _exportSpells || _exportSpawnPoints || _exportZoneAtlasEntries;
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

    private string GetDefaultPath()
    {
        var dir = Application.dataPath;
        return Path.Combine(dir, DEFAULT_FILENAME);
    }

    // --- Listeners ---
    private class AscensionScanListener : IAssetScanListener<Ascension> {
        public readonly List<AscensionDBRecord> Records = new();
        public void OnAssetFound(Ascension asset) {
            Debug.Log($"[AscensionScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from AscensionExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class BookExportCollector {
        public readonly List<BookDBRecord> Records = new();
        public void Collect() {
            Debug.Log("[BookExportCollector] Collect called");
            Records.Clear();
            // TODO: Port logic from BookExportStep using AllBooks.Books
        }
        public void Reset() => Records.Clear();
    }
    private class CharacterScanListener : IAssetScanListener<Character> {
        public readonly List<CharacterDBRecord> Records = new();
        public void OnAssetFound(Character component) {
            Debug.Log($"[CharacterScanListener] Found: {component?.name} ({component?.GetType().Name})");
            /* TODO: logic from CharacterExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class ClassScanListener : IAssetScanListener<Class> {
        public readonly List<ClassDBRecord> Records = new();
        public void OnAssetFound(Class asset) {
            Debug.Log($"[ClassScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from ClassExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class FactionScanListener : IAssetScanListener<WorldFaction> {
        public readonly List<FactionDBRecord> Records = new();
        public void OnAssetFound(WorldFaction asset) {
            Debug.Log($"[FactionScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from FactionExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class ItemScanListener : IAssetScanListener<Item> {
        public readonly List<ItemDBRecord> Records = new();
        public void OnAssetFound(Item asset) {
            Debug.Log($"[ItemScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from ItemExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class LootDropScanListener : IAssetScanListener<LootTable> {
        public readonly List<LootDropDBRecord> Records = new();
        public void OnAssetFound(LootTable asset) {
            Debug.Log($"[LootDropScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from LootDropExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class MiningNodeScanListener : IAssetScanListener<MiningNode> {
        public readonly List<MiningNodeDBRecord> Records = new();
        public void OnAssetFound(MiningNode component) {
            Debug.Log($"[MiningNodeScanListener] Found: {component?.name} ({component?.GetType().Name})");
            /* TODO: logic from MiningNodeExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class NPCDialogScanListener : IAssetScanListener<NPCDialog> {
        public readonly List<NPCDialogDBRecord> Records = new();
        public void OnAssetFound(NPCDialog asset) {
            Debug.Log($"[NPCDialogScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from NPCDialogExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class QuestScanListener : IAssetScanListener<Quest> {
        public readonly List<QuestDBRecord> Records = new();
        public void OnAssetFound(Quest asset) {
            Debug.Log($"[QuestScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from QuestExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class SkillScanListener : IAssetScanListener<Skill> {
        public readonly List<SkillDBRecord> Records = new();
        public void OnAssetFound(Skill asset) {
            Debug.Log($"[SkillScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from SkillExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class SpellScanListener : IAssetScanListener<Spell> {
        public readonly List<SpellDBRecord> Records = new();
        public void OnAssetFound(Spell asset) {
            Debug.Log($"[SpellScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from SpellExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class SpawnPointScanListener : IAssetScanListener<SpawnPoint> {
        public readonly List<SpawnPointDBRecord> Records = new();
        public void OnAssetFound(SpawnPoint comp) {
            Debug.Log($"[SpawnPointScanListener] Found: {comp?.name} ({comp?.GetType().Name})");
            /* TODO: logic from SpawnPointExportStep */
        }
        public void Reset() => Records.Clear();
    }
    private class ZoneAtlasEntryScanListener : IAssetScanListener<ZoneAtlasEntry> {
        public readonly List<ZoneAtlasEntryDBRecord> Records = new();
        public void OnAssetFound(ZoneAtlasEntry asset) {
            Debug.Log($"[ZoneAtlasEntryScanListener] Found: {asset?.name} ({asset?.GetType().Name})");
            /* TODO: logic from ZoneAtlasEntryExportStep */
        }
        public void Reset() => Records.Clear();
    }
}
