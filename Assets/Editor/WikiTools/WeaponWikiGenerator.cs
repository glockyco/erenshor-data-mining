using System;
using UnityEngine;
using UnityEditor;
using SQLite;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

public class WeaponWikiGenerator : EditorWindow
{
    // --- CONFIGURATION ---
    // Key to read the database path saved by DatabaseExporterWindow
    private const string EXPORTER_PREFS_KEY_DB_PATH = "Erenshor_DatabaseExporter_OutputPath";
    private const string DEFAULT_DB_FILENAME = "Erenshor.sqlite"; // Default filename if preference not set

    // List of ALL possible class names exactly as they appear in the ItemDBRecord.Classes field (comma-separated).
    // The generator will create a wiki parameter for each name in this list (e.g., |arcanist=True).
    private static readonly List<string> KnownClassNames = new()
    {
        "Arcanist", "Duelist", "Druid", "Paladin"
    };
    // --- END CONFIGURATION ---

    // --- UI State ---
    private string _statusMessage = "Ready. Click button to update weapon wiki templates in the database.";
    private MessageType _statusMessageType = MessageType.Info;
    private string _fullDbPathDisplay = ""; // For displaying the resolved path
    private bool _isRunning = false; // Prevent concurrent runs

    [MenuItem("Tools/Wiki/Update Weapon Wiki Templates")] // Changed menu item name slightly
    public static void ShowWindow()
    {
        WeaponWikiGenerator window = GetWindow<WeaponWikiGenerator>("Weapon Wiki Updater"); // Changed window title
        window.UpdateResolvedPath(); // Calculate path when window opens
        window.minSize = new Vector2(450, 250); // Reduced height as text area is removed
    }

    void OnEnable()
    {
        UpdateResolvedPath(); // Also update path when script reloads
    }

    // Gets the default path (relative to project root)
    private string GetDefaultDatabasePath()
    {
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", DEFAULT_DB_FILENAME));
    }

    void UpdateResolvedPath()
    {
        // Read the path from EditorPrefs, using the default path as a fallback
        string savedPath = EditorPrefs.GetString(EXPORTER_PREFS_KEY_DB_PATH, GetDefaultDatabasePath());
        _fullDbPathDisplay = Path.GetFullPath(savedPath); // Ensure it's a full path for display/use
    }

    void OnGUI()
    {
        GUILayout.Label("Update Weapon Wiki Templates in Database", EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // Display the resolved database path and check existence
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
        EditorGUI.BeginDisabledGroup(_isRunning || !dbExists); // Disable if running or DB doesn't exist
        if (GUILayout.Button("Update Weapon Wiki Templates in DB", GUILayout.Height(30)))
        {
            // Use ExecuteUpdate instead of GenerateWikiText
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

    // Renamed from GenerateWikiText to reflect new purpose
    private void ExecuteUpdate(string dbPath)
    {
        if (_isRunning) return; // Prevent concurrent execution

        _isRunning = true;
        _statusMessage = "Starting update process...";
        _statusMessageType = MessageType.Info;
        Repaint(); // Update UI

        List<ItemDBRecord> allItems;
        Dictionary<string, SpellDBRecord> spellData = new Dictionary<string, SpellDBRecord>();
        int updatedCount = 0;
        int weaponCount = 0;

        try
        {
            // Ensure the directory exists before trying to connect
            string dbDir = Path.GetDirectoryName(dbPath);
            if (!Directory.Exists(dbDir))
            {
                 throw new DirectoryNotFoundException($"Database directory not found: {dbDir}");
            }

            _statusMessage = $"Connecting to database: {dbPath}"; Repaint();
            Debug.Log($"Attempting to connect to database (ReadWrite): {dbPath}");
            // Connect with ReadWrite permissions and ability to Create table/columns
            using var db = new SQLiteConnection(dbPath, SQLiteOpenFlags.ReadWrite);

            // --- Load Data ---
            _statusMessage = "Reading items from database..."; Repaint();
            allItems = db.Table<ItemDBRecord>().ToList();
            Debug.Log($"Read {allItems.Count} items from database.");

            _statusMessage = "Reading spells from database..."; Repaint();
            spellData = db.Table<SpellDBRecord>().ToDictionary(s => s.Id, s => s);
            Debug.Log($"Loaded {spellData.Count} spell records for lookup.");

            // --- Filter & Process Weapons ---
            _statusMessage = "Identifying weapons..."; Repaint();
            List<ItemDBRecord> weapons = allItems.Where(IsWeaponRecord).ToList();
            weaponCount = weapons.Count;
            Debug.Log($"Found {weaponCount} weapon items based on IsWeaponRecord criteria.");

            if (weaponCount == 0)
            {
                _statusMessage = "No weapon items found in the database to update.";
                _statusMessageType = MessageType.Warning;
                _isRunning = false;
                Repaint();
                return;
            }

            _statusMessage = $"Generating templates and updating {weaponCount} weapons..."; Repaint();
            var itemsToUpdate = new List<ItemDBRecord>();

            foreach (var weapon in weapons)
            {
                string wikiTemplate = GenerateSingleWeaponTemplate(weapon, spellData);
                // Only update if the template changed or was null before
                if (weapon.WikiString != wikiTemplate)
                {
                    weapon.WikiString = wikiTemplate; // Update the object directly
                    itemsToUpdate.Add(weapon);
                }
            }

            // --- Update Database ---
            if (itemsToUpdate.Count > 0)
            {
                _statusMessage = $"Writing {itemsToUpdate.Count} updates to the database..."; Repaint();
                db.RunInTransaction(() =>
                {
                    // Use UpdateAll for efficiency if available and suitable, otherwise loop Update
                    // db.UpdateAll(itemsToUpdate); // Use if available and appropriate
                    foreach(var item in itemsToUpdate)
                    {
                        db.Update(item);
                    }
                });
                updatedCount = itemsToUpdate.Count;
                Debug.Log($"Successfully updated WikiTemplate for {updatedCount} items.");
            }
            else
            {
                Debug.Log("No weapon WikiTemplates needed updating.");
            }

            _statusMessage = $"Update complete. {updatedCount} out of {weaponCount} weapons had their WikiTemplate updated in the database.";
            _statusMessageType = MessageType.Info;

        }
        catch (System.Exception ex)
        {
            Debug.LogError($"Error during wiki template update: {ex.Message}\n{ex.StackTrace}");
            _statusMessage = $"ERROR: Update failed.\nReason: {ex.Message}\nCheck console for details.";
            _statusMessageType = MessageType.Error;
        }
        finally
        {
            _isRunning = false; // Ensure running flag is reset
            Repaint(); // Update UI with final status
        }
    }

    private bool IsWeaponRecord(ItemDBRecord record)
    {
        if (record == null)
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

    private int GetWikiTier(string quality)
    {
        return quality switch
        {
            "Normal" => 0,
            "Blessed" => 1,
            "Godly" => 2,
            _ => throw new ArgumentOutOfRangeException(nameof(quality), quality, null)
        };
    }

    private string GetWikiWeaponType(ItemDBRecord record)
    {
        if (record == null)
        {
            throw new ArgumentNullException(nameof(record));
        }

        if (record.ThisWeaponType is "TwoHandMelee" or "TwoHandStaff")
        {
            if (record.RequiredSlot == "Primary")
            {
                return "Primary - 2-Handed";
            }
            throw new ArgumentException($"Unexpected RequiredSlot '{record.RequiredSlot}' for 2-handed weapon type '{record.ThisWeaponType}'.");
        }

        return record.RequiredSlot switch
        {
            "PrimaryOrSecondary" => "Primary or Secondary",
            "Primary" => "Primary",
            "Secondary" => "Secondary",
            _ => throw new ArgumentException($"Unknown RequiredSlot: '{record.RequiredSlot}'.")
        };
    }

    private string GenerateSingleWeaponTemplate(ItemDBRecord record, Dictionary<string, SpellDBRecord> spellData)
    {
        var sb = new StringBuilder();
        // Use the exact template name from the description
        sb.AppendLine("{{Fancy-weapon");

        // --- image ---
        sb.AppendLine($"| image = [[File:{{{{PAGENAME}}}}.png|80px]]");

        // --- name ---
        // Uses ItemName directly. Template uses {{PAGENAME}} by default, this overrides it.
        sb.AppendLine($"| name = {{{{PAGENAME}}}}");

        // --- type ---
        sb.AppendLine($"| type = {GetWikiWeaponType(record)}");

        // --- relic ---
        sb.AppendLine($"| relic = {(record.Relic ? "True" : "")}");

        // --- Stats (str, end, dex, agi, int, wis, cha, res) ---
        sb.AppendLine($"| str = {record.Str}");
        sb.AppendLine($"| end = {record.End}");
        sb.AppendLine($"| dex = {record.Dex}");
        sb.AppendLine($"| agi = {record.Agi}");
        sb.AppendLine($"| int = {record.Int}");
        sb.AppendLine($"| wis = {record.Wis}");
        sb.AppendLine($"| cha = {record.Cha}");
        sb.AppendLine($"| res = {record.Res}"); // Resonance

        // --- Combat Stats (damage, delay, health, mana, armor) ---
        sb.AppendLine($"| damage = {(record.WeaponDmg != 0 ? record.WeaponDmg.ToString() : "")}");
        sb.AppendLine($"| delay = {(record.WeaponDly != 0 ? record.WeaponDly.ToString("0.##") : "")}");
        sb.AppendLine($"| health = {record.HP}");
        sb.AppendLine($"| mana = {record.Mana}");
        sb.AppendLine($"| armor = {record.AC}"); // AC mapped to armor

        // --- Resists (magic, poison, elemental, void) ---
        sb.AppendLine($"| magic = {record.MR}");
        sb.AppendLine($"| poison = {record.PR}");
        sb.AppendLine($"| elemental = {record.ER}");
        sb.AppendLine($"| void = {record.VR}");

        // --- description ---
        // Use Lore field, escape wiki markup. Template default handles empty.
        if (!string.IsNullOrEmpty(record.Lore))
        {
            sb.AppendLine($"| description = {EscapeWikiText(record.Lore)}");
        }

        // --- base_dps ---
        // OMIT - Template calculates this automatically.

        // --- classes ---
        var allowedClasses = new HashSet<string>(
            (record.Classes ?? "").Split(new[] { ',', ' ' }, StringSplitOptions.RemoveEmptyEntries),
            StringComparer.OrdinalIgnoreCase // Case-insensitive matching
        );
        foreach (string className in KnownClassNames)
        {
            sb.AppendLine($"| {className.ToLower()} = {(allowedClasses.Contains(className) ? "True" : "")}");
        }

        // --- Proc Handling ---
        string procOnHitId = record.WeaponProcOnHitId;
        string wornEffectId = record.WornEffectId;

        string procStyle = "";
        SpellDBRecord procSpell = null;

        // Determine the proc source and style
        // Prioritize On Hit proc over Worn effect if both somehow exist
        
        if (!string.IsNullOrEmpty(procOnHitId))
        {
            procStyle = record.Shield ? "Bash" : "Attack";
            procSpell = spellData[procOnHitId];
        }
        else if (!string.IsNullOrEmpty(wornEffectId))
        {
            procStyle = "Worn";
            procSpell = spellData[wornEffectId];
        }
        
        // Output proc parameters only if a valid proc spell was found
        // proc_name
        sb.AppendLine($"| proc_name = {(procSpell != null ? "[[" + EscapeWikiText(procSpell.SpellName) + "]]" : "")}");

        // proc_desc
        var procDesc = !string.IsNullOrEmpty(procSpell?.SpellDesc) ? EscapeWikiText(procSpell.SpellDesc) : "";
        sb.AppendLine($"| proc_desc = {procDesc}");

        // proc_style
        sb.AppendLine($"| proc_style = {procStyle ?? ""}");

        // proc_chance - Output always, empty if not Attack or <= 0
        string procChance = record.WeaponProcChance > 0 ? record.WeaponProcChance.ToString(CultureInfo.InvariantCulture) : "";
        sb.AppendLine($"| proc_chance = {procChance}");
        
        // --- tier ---
        sb.AppendLine($"| tier = {GetWikiTier(record.Quality)}");

        // --- Final Closing Braces ---
        sb.Append("}}");
        return sb.ToString();
    }

    private string EscapeWikiText(string text)
    {
        if (string.IsNullOrEmpty(text)) return "";
        return text.Replace("|", "&#124;")
                   .Replace("=", "&#61;")
                   .Replace("\n", "<br>");
    }
}
