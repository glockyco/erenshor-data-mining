using System;
using UnityEngine;
using UnityEditor;
using SQLite;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

public class ItemWikiGenerator : EditorWindow
{
    // --- CONFIGURATION ---
    private const string EXPORTER_PREFS_KEY_DB_PATH = "Erenshor_DatabaseExporter_OutputPath";
    private const string DEFAULT_DB_FILENAME = "Erenshor.sqlite"; // Default filename if preference not set

    // List of ALL possible class names exactly as they appear in the ItemDBRecord.Classes field (comma-separated).
    // The generator will create a wiki parameter for each name in this list (e.g., |arcanist=True).
    private static readonly List<string> KnownClassNames = new()
    {
        "Arcanist", "Duelist", "Druid", "Paladin"
    };

    // Define which slots are considered armor
    private static readonly HashSet<string> ArmorSlots = new(StringComparer.OrdinalIgnoreCase)
    {
        "Charm", "Head", "Neck", "Ring", "Hand", "Chest", "Arm", "Bracer", "Leg", "Waist", "Foot", "Back"
    };
    // --- END CONFIGURATION ---

    // --- UI State ---
    private string _statusMessage = "Ready. Click button to update item wiki templates in the database."; // Updated message
    private MessageType _statusMessageType = MessageType.Info;
    private string _fullDbPathDisplay = ""; // For displaying the resolved path
    private bool _isRunning = false; // Prevent concurrent runs

    [MenuItem("Tools/Wiki/Update Item Wiki Templates")] // Updated menu item name
    public static void ShowWindow()
    {
        // Use the updated class name here
        ItemWikiGenerator window = GetWindow<ItemWikiGenerator>("Item Wiki Updater"); // Updated window title
        window.UpdateResolvedPath(); // Calculate path when window opens
        window.minSize = new Vector2(450, 250);
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
        GUILayout.Label("Update Item Wiki Templates in Database", EditorStyles.boldLabel); // Updated label
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
        // Updated button text
        if (GUILayout.Button("Update Item Wiki Templates in DB", GUILayout.Height(30)))
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
        if (_isRunning) return; // Prevent concurrent execution

        _isRunning = true;
        _statusMessage = "Starting update process...";
        _statusMessageType = MessageType.Info;
        Repaint(); // Update UI

        List<ItemDBRecord> allItems;
        Dictionary<string, SpellDBRecord> spellData;
        int updatedCount = 0;
        int processedItemCount = 0; // Count both weapons and armor

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

            // --- Filter & Process Items (Weapons and Armor) ---
            _statusMessage = "Identifying weapons and armor..."; Repaint();
            // Filter items that are either weapons or armor
            List<ItemDBRecord> processableItems = allItems.Where(item => IsWeaponRecord(item) || IsArmorRecord(item)).ToList();
            processedItemCount = processableItems.Count;
            Debug.Log($"Found {processedItemCount} weapon or armor items based on slot criteria.");

            if (processedItemCount == 0)
            {
                _statusMessage = "No weapon or armor items found in the database to update.";
                _statusMessageType = MessageType.Warning;
                _isRunning = false;
                Repaint();
                return;
            }

            _statusMessage = $"Generating templates and updating {processedItemCount} items..."; Repaint();
            var itemsToUpdate = new List<ItemDBRecord>();

            foreach (var item in processableItems)
            {
                string wikiTemplate = "";
                // Determine which template to generate
                if (IsWeaponRecord(item))
                {
                    wikiTemplate = GenerateSingleWeaponTemplate(item, spellData);
                }
                else if (IsArmorRecord(item))
                {
                    wikiTemplate = GenerateSingleArmorTemplate(item, spellData);
                }
                else
                {
                    // Should not happen due to prior filtering, but good practice
                    continue;
                }

                // Only update if the template changed or was null before
                if (item.WikiString != wikiTemplate)
                {
                    item.WikiString = wikiTemplate; // Update the object directly
                    itemsToUpdate.Add(item);
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
                Debug.Log("No item WikiTemplates needed updating.");
            }

            // Updated status message
            _statusMessage = $"Update complete. {updatedCount} out of {processedItemCount} items had their WikiTemplate updated in the database.";
            _statusMessageType = MessageType.Info;

        }
        catch (Exception ex)
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

    // --- Tier and Type Helpers ---

    private int GetWikiTier(string quality)
    {
        return quality switch
        {
            "Normal" => 0,
            "Blessed" => 1,
            "Godly" => 2,
            // Default to 0 or throw if quality is unexpected/missing
            _ => 0 // Or: throw new ArgumentOutOfRangeException(nameof(quality), quality, "Unknown quality value for tier calculation.")
        };
    }

    private string GetWikiWeaponType(ItemDBRecord record)
    {
        if (record == null)
        {
            throw new ArgumentNullException(nameof(record));
        }

        // Handle 2-Handed specifically based on ThisWeaponType and RequiredSlot
        if (record.ThisWeaponType is "TwoHandMelee" or "TwoHandStaff")
        {
            if (record.RequiredSlot == "Primary")
            {
                return "Primary - 2-Handed";
            }
            throw new ArgumentException($"Unexpected RequiredSlot '{record.RequiredSlot}' for 2-handed weapon type '{record.ThisWeaponType}'.");
        }

        // Handle other weapon slots
        return record.RequiredSlot switch
        {
            "PrimaryOrSecondary" => "Primary or Secondary",
            "Primary" => "Primary",
            "Secondary" => "Secondary",
            _ => throw new ArgumentException($"Unknown RequiredSlot for weapon: '{record.RequiredSlot}'.")
        };
    }

    // --- Template Generation ---

    private string GenerateSingleWeaponTemplate(ItemDBRecord record, Dictionary<string, SpellDBRecord> spellData)
    {
        var sb = new StringBuilder();
        sb.AppendLine("{{Fancy-weapon");

        // --- image ---
        sb.AppendLine($"| image = [[File:{{{{PAGENAME}}}}.png|80px]]");

        // --- name ---
        sb.AppendLine($"| name = {{{{PAGENAME}}}}");

        // --- type ---
        sb.AppendLine($"| type = {GetWikiWeaponType(record)}");

        // --- relic ---
        sb.AppendLine($"| relic = {(record.Relic ? "True" : "")}");

        // --- Stats (str, end, dex, agi, int, wis, cha, res) ---
        AppendStatParameters(sb, record);

        // --- Combat Stats (damage, delay, health, mana, armor) ---
        sb.AppendLine($"| damage = {(record.WeaponDmg != 0 ? record.WeaponDmg.ToString() : "")}");
        sb.AppendLine($"| delay = {(record.WeaponDly != 0 ? record.WeaponDly.ToString("0.##", CultureInfo.InvariantCulture) : "")}");
        sb.AppendLine($"| health = {record.HP}");
        sb.AppendLine($"| mana = {record.Mana}");
        sb.AppendLine($"| armor = {record.AC}");

        // --- Resists (magic, poison, elemental, void) ---
        AppendResistParameters(sb, record);

        // --- description ---
        if (!string.IsNullOrEmpty(record.Lore))
        {
            sb.AppendLine($"| description = {EscapeWikiText(record.Lore.Trim())}");
        }

        // --- base_dps --- OMITTED (Template calculates)

        // --- classes ---
        AppendClassParameters(sb, record);

        // --- Proc Handling ---
        string procOnHitId = record.WeaponProcOnHitId;
        string wornEffectId = record.WornEffectId;
        string procStyle = "";
        SpellDBRecord procSpell = null;

        if (!string.IsNullOrEmpty(procOnHitId) && spellData.TryGetValue(procOnHitId, out procSpell))
        {
            procStyle = record.Shield ? "Bash" : "Attack";
        }
        else if (!string.IsNullOrEmpty(wornEffectId) && spellData.TryGetValue(wornEffectId, out procSpell))
        {
            procStyle = "Worn";
        }

        // Output proc parameters only if a valid proc spell was found
        sb.AppendLine($"| proc_name = {(procSpell != null ? "[[" + EscapeWikiText(procSpell.SpellName) + "]]" : "")}");
        var procDesc = procSpell?.SpellDesc ?? "";
        sb.AppendLine($"| proc_desc = {(string.IsNullOrEmpty(procDesc) ? "" : EscapeWikiText(procDesc))}");
        string procChance = record.WeaponProcChance > 0 ? record.WeaponProcChance.ToString(CultureInfo.InvariantCulture) : "";
        sb.AppendLine($"| proc_chance = {procChance}");
        sb.AppendLine($"| proc_style = {procStyle ?? ""}");

        // --- tier ---
        sb.AppendLine($"| tier = {GetWikiTier(record.Quality)}");

        // --- Final Closing Braces ---
        sb.Append("}}");
        return sb.ToString();
    }

    private string GenerateSingleArmorTemplate(ItemDBRecord record, Dictionary<string, SpellDBRecord> spellData)
    {
        var sb = new StringBuilder();
        sb.AppendLine("{{Fancy-armor");

        // --- image ---
        sb.AppendLine($"| image = [[File:{{{{PAGENAME}}}}.png|80px]]");

        // --- name ---
        sb.AppendLine($"| name = {{{{PAGENAME}}}}");

        // --- slot ---
        sb.AppendLine($"| slot = {record.RequiredSlot}");

        // --- relic ---
        sb.AppendLine($"| relic = {(record.Relic ? "True" : "")}");

        // --- Stats (str, end, dex, agi, int, wis, cha, res) ---
        AppendStatParameters(sb, record);

        // --- Combat Stats (health, mana, armor) ---
        sb.AppendLine($"| health = {record.HP}");
        sb.AppendLine($"| mana = {record.Mana}");
        sb.AppendLine($"| armor = {record.AC}");

        // --- Resists (magic, poison, elemental, void) ---
        AppendResistParameters(sb, record);

        // --- description ---
        if (!string.IsNullOrEmpty(record.Lore))
        {
            sb.AppendLine($"| description = {EscapeWikiText(record.Lore.Trim())}");
        }

        // --- classes ---
        AppendClassParameters(sb, record);

        // --- Proc Handling ---
        string procOnHitId = record.WeaponProcOnHitId;
        string wornEffectId = record.WornEffectId;
        string onClickEffectId = record.ItemEffectOnClickId;
        string procStyle = "";
        SpellDBRecord procSpell = null;

        if (!string.IsNullOrEmpty(onClickEffectId) && spellData.TryGetValue(onClickEffectId, out procSpell))
        {
            procStyle = "Activatable";
        }
        else if (!string.IsNullOrEmpty(wornEffectId) && spellData.TryGetValue(wornEffectId, out procSpell))
        {
            procStyle = "Worn";
        }
        else if (!string.IsNullOrEmpty(procOnHitId) && spellData.TryGetValue(procOnHitId, out procSpell))
        {
            procStyle = "Cast";
        }

        // Output proc parameters only if a valid proc spell was found
        sb.AppendLine($"| proc_name = {(procSpell != null ? "[[" + EscapeWikiText(procSpell.SpellName) + "]]" : "")}");
        var procDesc = procSpell?.SpellDesc ?? "";
        sb.AppendLine($"| proc_desc = {(string.IsNullOrEmpty(procDesc) ? "" : EscapeWikiText(procDesc))}");
        string procChance = record.WeaponProcChance > 0 ? record.WeaponProcChance.ToString(CultureInfo.InvariantCulture) : "";
        sb.AppendLine($"| proc_chance = {procChance}");
        sb.AppendLine($"| proc_style = {procStyle ?? ""}");

        // --- tier ---
        sb.AppendLine($"| tier = {GetWikiTier(record.Quality)}");

        // --- Final Closing Braces ---
        sb.Append("}}");
        return sb.ToString();
    }

    // --- Helper Methods for Template Generation ---

    private void AppendStatParameters(StringBuilder sb, ItemDBRecord record)
    {
        sb.AppendLine($"| str = {record.Str}");
        sb.AppendLine($"| end = {record.End}");
        sb.AppendLine($"| dex = {record.Dex}");
        sb.AppendLine($"| agi = {record.Agi}");
        sb.AppendLine($"| int = {record.Int}");
        sb.AppendLine($"| wis = {record.Wis}");
        sb.AppendLine($"| cha = {record.Cha}");
        sb.AppendLine($"| res = {record.Res}");
    }

    private void AppendResistParameters(StringBuilder sb, ItemDBRecord record)
    {
        sb.AppendLine($"| magic = {record.MR}");
        sb.AppendLine($"| poison = {record.PR}");
        sb.AppendLine($"| elemental = {record.ER}");
        sb.AppendLine($"| void = {record.VR}");
    }

    private void AppendClassParameters(StringBuilder sb, ItemDBRecord record)
    {
        var allowedClasses = new HashSet<string>(
            (record.Classes ?? "").Split(new[] { ',', ' ' }, StringSplitOptions.RemoveEmptyEntries),
            StringComparer.OrdinalIgnoreCase // Case-insensitive matching
        );
        foreach (string className in KnownClassNames)
        {
            // Ensure parameter name is lowercase as per templates
            sb.AppendLine($"| {className.ToLowerInvariant()} = {(allowedClasses.Contains(className) ? "True" : "")}");
        }
    }

    private string EscapeWikiText(string text)
    {
        if (string.IsNullOrEmpty(text)) return "";
        return text.Replace("|", "&#124;")
                   .Replace("=", "&#61;")
                   .Replace("\n", "<br>");
    }
}
