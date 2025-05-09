using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using SQLite;
using UnityEditor;
using UnityEngine;

public class ItemWikiGenerator : EditorWindow
{
    // --- CONFIGURATION ---
    private const string EditorPrefsKeyPath = "Erenshor_AssetScannerExporter_OutputPath";
    private const string DefaultFilename = "Erenshor.sqlite";

    private static readonly HashSet<string> ArmorSlots = new(StringComparer.OrdinalIgnoreCase)
    {
        "Charm", "Head", "Neck", "Ring", "Hand", "Chest", "Arm", "Bracer", "Leg", "Waist", "Foot", "Back"
    };
    // --- END CONFIGURATION ---

    // --- UI State ---
    private string _statusMessage = "Ready. Click button to update item WikiStrings in the database.";
    private MessageType _statusMessageType = MessageType.Info;
    private string _fullDbPathDisplay = "";
    private bool _isRunning = false;

    [MenuItem("Tools/Wiki/Update Item WikiStrings")] // Updated menu item name
    public static void ShowWindow()
    {
        ItemWikiGenerator window = GetWindow<ItemWikiGenerator>("Item Wiki Updater");
        window.UpdateResolvedPath();
        window.minSize = new Vector2(450, 250);
    }

    void OnEnable()
    {
        UpdateResolvedPath();
    }

    void UpdateResolvedPath()
    {
        _fullDbPathDisplay = EditorPrefs.GetString(EditorPrefsKeyPath, Path.Combine(Application.dataPath, DefaultFilename));
    }

    void OnGUI()
    {
        GUILayout.Label("Update Item WikiStrings in Database", EditorStyles.boldLabel); // Updated label
        EditorGUILayout.Space();

        GUILayout.Label("Database Path (Shared with Exporter):", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(_fullDbPathDisplay, MessageType.None);

        bool dbExists = File.Exists(_fullDbPathDisplay);
        if (!dbExists)
        {
            EditorGUILayout.HelpBox($"Database file not found!\nPlease ensure the export has run via 'Tools > Database > Export Database' and the path is correctly set there.", MessageType.Error);
        }

        EditorGUILayout.Space();

        // --- Status Display ---
        EditorGUILayout.LabelField("Status:", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(_statusMessage, _statusMessageType);
        EditorGUILayout.Space();

        // --- Action Button ---
        EditorGUI.BeginDisabledGroup(_isRunning || !dbExists);
        if (GUILayout.Button("Update Item WikiStrings in DB", GUILayout.Height(30)))
        {
            ExecuteUpdate(_fullDbPathDisplay);
        }
        EditorGUI.EndDisabledGroup();

        // --- Utility Button ---
        EditorGUI.BeginDisabledGroup(_isRunning || !dbExists);
        if (GUILayout.Button("Open Output Folder"))
        {
            EditorUtility.RevealInFinder(_fullDbPathDisplay);
        }
        EditorGUI.EndDisabledGroup();
    }

    private void ExecuteUpdate(string dbPath)
    {
        if (_isRunning) return;

        _isRunning = true;
        _statusMessage = "Starting update process...";
        _statusMessageType = MessageType.Info;
        Repaint();

        try
        {
            string dbDir = Path.GetDirectoryName(dbPath);
            if (!Directory.Exists(dbDir))
            {
                 throw new DirectoryNotFoundException($"Database directory not found: {dbDir}");
            }

            _statusMessage = $"Connecting to database: {dbPath}"; Repaint();
            Debug.Log($"Attempting to connect to database (ReadWrite): {dbPath}");
            using var db = new SQLiteConnection(dbPath, SQLiteOpenFlags.ReadWrite);

            // --- Load Data ---
            _statusMessage = "Reading items from database..."; Repaint();
            var allItems = db.Table<ItemDBRecord>().ToList();
            Debug.Log($"Read {allItems.Count} items from database.");

            // --- Filter & Process Items (Weapons and Armor) ---
            _statusMessage = "Identifying weapons and armor..."; Repaint();
            List<ItemDBRecord> processableItems = allItems.Where(item => IsWeaponRecord(item) || IsArmorRecord(item)).ToList();
            Debug.Log($"Found {processableItems.Count} weapon or armor items based on slot criteria.");

            if (processableItems.Count == 0)
            {
                _statusMessage = "No weapon or armor items found in the database to update.";
                _statusMessageType = MessageType.Warning;
                _isRunning = false;
                Repaint();
                return;
            }

            _statusMessage = $"Generating templates and updating {processableItems.Count} items..."; Repaint();
            var itemsToUpdate = new List<ItemDBRecord>();

            foreach (var item in processableItems)
            {
                string wikiTemplate;
                if (IsWeaponRecord(item))
                {
                    wikiTemplate = new WikiFancyWeaponFactory().Create(item).ToString();
                }
                else if (IsArmorRecord(item))
                {
                    wikiTemplate = new WikiFancyArmorFactory().Create(item).ToString();
                }
                else
                {
                    throw new InvalidOperationException(
                        $"Item with ID '{item.Id}' is neither a weapon nor an armor record. This should have been filtered out earlier."
                    );
                }

                if (item.WikiString != wikiTemplate)
                {
                    item.WikiString = wikiTemplate;
                    itemsToUpdate.Add(item);
                }
            }

            // --- Update Database ---
            if (itemsToUpdate.Count > 0)
            {
                _statusMessage = $"Writing {itemsToUpdate.Count} updates to the database..."; Repaint();
                db.UpdateAll(itemsToUpdate);
                Debug.Log($"Successfully updated WikiString for {itemsToUpdate.Count} items.");
            }
            else
            {
                Debug.Log("No item WikiStrings needed updating.");
            }

            _statusMessage = $"Update complete. {itemsToUpdate.Count} out of {processableItems.Count} items had their WikiString updated in the database.";
            _statusMessageType = MessageType.Info;

        }
        catch (Exception ex)
        {
            Debug.LogError($"Error during WikiString update: {ex.Message}\n{ex.StackTrace}");
            _statusMessage = $"ERROR: Update failed.\nReason: {ex.Message}\nCheck console for details.";
            _statusMessageType = MessageType.Error;
        }
        finally
        {
            _isRunning = false;
            Repaint();
        }
    }

    // --- Item Type Identification ---

    private bool IsWeaponRecord(ItemDBRecord record)
    {
        if (record == null || string.IsNullOrEmpty(record.RequiredSlot))
        {
            return false;
        }

        return record.RequiredSlot switch
        {
            "PrimaryOrSecondary" => true,
            "Primary" => true,
            "Secondary" => true,
            _ => false
        };
    }

    private bool IsArmorRecord(ItemDBRecord record)
    {
        if (record == null || string.IsNullOrEmpty(record.RequiredSlot))
        {
            return false;
        }
        return ArmorSlots.Contains(record.RequiredSlot);
    }
}
