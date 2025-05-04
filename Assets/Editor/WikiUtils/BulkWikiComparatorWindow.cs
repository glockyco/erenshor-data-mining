using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using UnityEditor;
using UnityEditor.IMGUI.Controls;
using UnityEngine;
using SQLite;

public class BulkWikiComparatorWindow : EditorWindow
{
    // --- Configuration ---
    private const string EXPORTER_PREFS_KEY_DB_PATH = "Erenshor_DatabaseExporter_OutputPath";
    private const string DEFAULT_DB_FILENAME = "Erenshor.sqlite";
    // --- End Configuration ---

    // TreeView state
    [SerializeField] private TreeViewState? _treeViewState;
    [SerializeField] private MultiColumnHeaderState? _multiColumnHeaderState;
    private BulkComparisonTreeView? _treeView;
    private SearchField? _searchField;

    // Window state
    private string _fullDbPathDisplay = "";
    private bool _isComparing = false;
    private float _progress = 0f;
    private string _progressMessage = "";
    private string _summaryMessage = "Ready. Click 'Compare All' to start.";
    private CancellationTokenSource? _cancellationTokenSource;
    private List<ComparisonResultItem> _comparisonResults = new List<ComparisonResultItem>();

    // Detail view state (optional, for showing selected item details)
    private ComparisonResultItem? _selectedItem = null;
    private Vector2 _scrollPosLocal;
    private Vector2 _scrollPosOnline;

    [MenuItem("Tools/Wiki/Bulk Wiki Comparator")]
    public static void ShowWindow()
    {
        BulkWikiComparatorWindow window = GetWindow<BulkWikiComparatorWindow>("Bulk Wiki Comparator");
        window.minSize = new Vector2(800, 500);
    }

    // --- Initialization and Path Handling ---

    void OnEnable()
    {
        UpdateResolvedPath();
        InitializeTreeView();
        InitializeSearchField();
    }

    void OnDisable()
    {
        // Cancel any ongoing comparison when the window is closed or disabled
        _cancellationTokenSource?.Cancel();
        _cancellationTokenSource?.Dispose();
        _cancellationTokenSource = null;
    }

    private string GetDefaultDatabasePath()
    {
        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", DEFAULT_DB_FILENAME));
    }

    void UpdateResolvedPath()
    {
        string savedPath = EditorPrefs.GetString(EXPORTER_PREFS_KEY_DB_PATH, GetDefaultDatabasePath());
        _fullDbPathDisplay = Path.GetFullPath(savedPath);
    }

    void InitializeTreeView()
    {
        // Ensure states are created if null
        _treeViewState ??= new TreeViewState();

        var headerState = BulkComparisonTreeView.CreateMultiColumnHeaderState();
        if (MultiColumnHeaderState.CanOverwriteSerializedFields(_multiColumnHeaderState, headerState))
        {
            MultiColumnHeaderState.OverwriteSerializedFields(_multiColumnHeaderState, headerState);
        }

        _multiColumnHeaderState = headerState;

        var multiColumnHeader = new MultiColumnHeader(headerState);
        multiColumnHeader.sortingChanged += OnSortingChanged; // Hook up sorting

        _treeView = new BulkComparisonTreeView(_treeViewState, multiColumnHeader, _comparisonResults);
        _treeView.OnSelectionChangedCallback += OnTreeViewSelectionChanged;

        // Initial sort
        multiColumnHeader.SetSorting(1, true);
        OnSortingChanged(multiColumnHeader); // Apply initial sort
    }

    void InitializeSearchField()
    {
        _searchField ??= new SearchField();
    }

    // --- GUI Drawing ---

    private void OnGUI()
    {
        DrawTopControls();
        DrawTreeView();
        DrawDetailView(); // Optional: Draw details for selected item
    }

    private void DrawTopControls()
    {
        EditorGUILayout.LabelField("Bulk Compare Local Item WikiStrings with Online Wiki Pages",
            EditorStyles.boldLabel);
        EditorGUILayout.Space();

        // Database Path
        GUILayout.Label("Database Path (Shared with Exporter):", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(_fullDbPathDisplay, MessageType.None);

        bool dbExists = File.Exists(_fullDbPathDisplay);
        if (!dbExists)
        {
            EditorGUILayout.HelpBox(
                $"Database file not found! Please ensure the export has run ('Tools > Database > Export Database') and the path is correct.",
                MessageType.Error);
        }

        EditorGUILayout.Space();

        // Action Button & Progress
        using (new EditorGUILayout.HorizontalScope())
        {
            EditorGUI.BeginDisabledGroup(_isComparing || !dbExists);
            if (GUILayout.Button(_isComparing ? "Comparing..." : "Compare All Items with WikiStrings",
                    GUILayout.Height(30)))
            {
                // Start comparison
                CompareAllItemsAsync();
            }

            EditorGUI.EndDisabledGroup();

            if (_isComparing)
            {
                if (GUILayout.Button("Cancel", GUILayout.Width(80), GUILayout.Height(30)))
                {
                    _cancellationTokenSource?.Cancel();
                    // State will be reset in the async method's finally block
                }
            }
        }

        // Progress Bar and Message
        if (_isComparing || _progress > 0) // Show progress bar if comparing or if comparison finished
        {
            EditorGUILayout.Space();
            Rect r = EditorGUILayout.GetControlRect(false, EditorGUIUtility.singleLineHeight);
            EditorGUI.ProgressBar(r, _progress, _progressMessage);
            EditorGUILayout.Space();
        }

        // Summary Message
        EditorGUILayout.LabelField("Status:", EditorStyles.boldLabel);
        EditorGUILayout.HelpBox(_summaryMessage, MessageType.Info);
        EditorGUILayout.Space();

        // Search Field
        if (_searchField != null && _treeView != null)
        {
            _treeView.searchString = _searchField.OnGUI(_treeView.searchString);
        }

        EditorGUILayout.Space();
    }

    private void DrawTreeView()
    {
        // Calculate rect for the TreeView
        // Reserve space for bottom detail view if needed, otherwise use remaining space
        float detailViewHeight = _selectedItem != null ? Mathf.Max(200, position.height * 0.3f) : 0;
        Rect treeViewRect = GUILayoutUtility.GetRect(GUIContent.none, GUIStyle.none, GUILayout.ExpandWidth(true),
            GUILayout.ExpandHeight(true));
        if (detailViewHeight > 0)
        {
            treeViewRect.height -=
                (detailViewHeight +
                 EditorGUIUtility.standardVerticalSpacing * 2); // Adjust height for detail view and spacing
        }

        _treeView?.OnGUI(treeViewRect);
    }

    private void DrawDetailView()
    {
        if (_selectedItem == null) return;

        EditorGUILayout.Space(); // Space before the detail section
        EditorGUILayout.LabelField($"Details for: {_selectedItem.ItemName} ({_selectedItem.ItemId})",
            EditorStyles.boldLabel);

        // Use a flexible space that takes up the reserved height
        using (EditorGUILayout.HorizontalScope scope =
               new EditorGUILayout.HorizontalScope(GUILayout.ExpandHeight(true)))
        {
            // --- Local Text ---
            EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField("Local WikiString (Relevant Template)", EditorStyles.miniBoldLabel);
            _scrollPosLocal = EditorGUILayout.BeginScrollView(_scrollPosLocal, EditorStyles.helpBox,
                GUILayout.ExpandHeight(true));
            EditorGUILayout.TextArea(_selectedItem.DisplayLocalText ?? "N/A", EditorStyles.textArea,
                GUILayout.ExpandHeight(true));
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();

            // --- Online Text ---
            EditorGUILayout.BeginVertical(GUILayout.ExpandWidth(true));
            EditorGUILayout.LabelField("Online Wiki Text (Relevant Template)", EditorStyles.miniBoldLabel);
            _scrollPosOnline = EditorGUILayout.BeginScrollView(_scrollPosOnline, EditorStyles.helpBox,
                GUILayout.ExpandHeight(true));
            EditorGUILayout.TextArea(_selectedItem.DisplayOnlineText ?? "N/A", EditorStyles.textArea,
                GUILayout.ExpandHeight(true));
            EditorGUILayout.EndScrollView();
            EditorGUILayout.EndVertical();
        }
    }


    // --- Comparison Logic ---

    private async void CompareAllItemsAsync()
    {
        if (_isComparing) return;
        if (!File.Exists(_fullDbPathDisplay))
        {
            _summaryMessage = "Database file not found. Cannot start comparison.";
            Repaint();
            return;
        }

        _isComparing = true;
        _progress = 0f;
        _progressMessage = "Querying database...";
        _summaryMessage = "Starting comparison...";
        _selectedItem = null; // Clear selection when starting new bulk compare
        _comparisonResults.Clear(); // Clear previous results
        _treeView?.SetResults(_comparisonResults); // Update treeview immediately
        Repaint();

        _cancellationTokenSource?.Dispose();
        _cancellationTokenSource = new CancellationTokenSource();
        var token = _cancellationTokenSource.Token;

        List<ItemDBRecord> itemsToCompare = new List<ItemDBRecord>();
        WikiComparator comparator = new WikiComparator();

        try
        {
            // --- Step 1: Query Database (on background thread) ---
            await Task.Run(() =>
            {
                SQLiteConnection? db = null;
                try
                {
                    db = new SQLiteConnection(_fullDbPathDisplay, SQLiteOpenFlags.ReadOnly);
                    itemsToCompare = db.Table<ItemDBRecord>().Where(item => !string.IsNullOrEmpty(item.WikiString))
                        .ToList();
                }
                catch (Exception ex)
                {
                    Debug.LogError($"[BulkWikiComparator] Error querying database: {ex}");
                    // Update UI on main thread
                    EditorApplication.delayCall += () =>
                    {
                        _summaryMessage = $"Database Query Error: {ex.Message}";
                        _isComparing = false; // Stop the process
                        Repaint();
                    };
                    itemsToCompare.Clear(); // Ensure list is empty if query failed
                }
                finally
                {
                    db?.Close();
                    db?.Dispose();
                }
            }, token); // Pass token to Task.Run

            if (token.IsCancellationRequested || !itemsToCompare.Any())
            {
                if (!itemsToCompare.Any() && !token.IsCancellationRequested)
                {
                    _summaryMessage = "No items with WikiStrings found in the database.";
                }

                // Reset state in finally block
                return;
            }

            // Initialize results list with pending items on main thread
            InitializeResultsList(itemsToCompare);
            _treeView?.SetResults(_comparisonResults); // Update treeview with pending items
            _treeView?.Reload();
            Repaint();


            // --- Step 2: Compare Each Item (asynchronously) ---
            int totalItems = itemsToCompare.Count;
            int processedCount = 0;
            int matchCount = 0;
            int mismatchCount = 0;
            int errorCount = 0;
            int localEmptyCount = 0;

            // Use a semaphore to limit concurrency (optional, but good practice for external calls)
            int maxConcurrentTasks = 10; // Adjust as needed
            using (var semaphore = new SemaphoreSlim(maxConcurrentTasks))
            {
                List<Task> comparisonTasks = new List<Task>();

                for (int i = 0; i < totalItems; i++)
                {
                    if (token.IsCancellationRequested) break;

                    await semaphore.WaitAsync(token); // Wait if max concurrency is reached

                    int index = i; // Capture loop variable for closure
                    ComparisonResultItem resultItem = _comparisonResults[index]; // Get the placeholder item

                    comparisonTasks.Add(Task.Run<Task>(async () =>
                    {
                        try
                        {
                            if (token.IsCancellationRequested) return;

                            string wikiPageName = resultItem.ItemName.Replace(" ", "_"); // Basic space replacement
                            string baseUrl = $"https://erenshor.wiki.gg/wiki/{Uri.EscapeDataString(wikiPageName)}";

                            var result =
                                await comparator.CompareWikiStringAsync(baseUrl, resultItem.LocalWikiString);

                            // Update the result item directly
                            resultItem.DisplayOnlineText = result.DisplayOnlineText;
                            resultItem.DisplayLocalText = result.DisplayLocalText; // Update local display text too
                            resultItem.Details = result.ErrorMessage ?? (result.AreEqual ? "Match" : "Mismatch");

                            if (token.IsCancellationRequested) return;

                            // Determine status based on result
                            if (result.AreEqual)
                            {
                                // Check if it was a match because local was empty/no template
                                if (result.DisplayLocalText != null && result.DisplayLocalText.StartsWith("<"))
                                {
                                    resultItem.Status = ComparisonStatus.LocalEmpty;
                                    Interlocked.Increment(ref localEmptyCount);
                                }
                                else
                                {
                                    resultItem.Status = ComparisonStatus.Match;
                                    Interlocked.Increment(ref matchCount);
                                }
                            }
                            else
                            {
                                // Distinguish between content mismatch and fetch/parse errors
                                if (result.ErrorMessage != null &&
                                    (result.ErrorMessage.Contains("missing online") ||
                                     result.ErrorMessage.Contains("Fetch Failed") ||
                                     result.ErrorMessage.Contains("Internal error") ||
                                     result.ErrorMessage.Contains("not found on wiki")))
                                {
                                    resultItem.Status = ComparisonStatus.Error;
                                    Interlocked.Increment(ref errorCount);
                                }
                                else // Likely a content mismatch
                                {
                                    resultItem.Status = ComparisonStatus.Mismatch;
                                    Interlocked.Increment(ref mismatchCount);
                                }
                            }
                        }
                        catch (Exception ex)
                        {
                            Debug.LogError($"[BulkWikiComparator] Error comparing item {resultItem.ItemId}: {ex}");
                            resultItem.Status = ComparisonStatus.Error;
                            resultItem.Details = $"Unexpected Error: {ex.Message}";
                            Interlocked.Increment(ref errorCount);
                        }
                        finally
                        {
                            semaphore.Release();
                            int currentProcessed = Interlocked.Increment(ref processedCount);

                            // Update progress on the main thread periodically
                            if (currentProcessed % 5 == 0 ||
                                currentProcessed == totalItems) // Update every 5 items or on the last one
                            {
                                EditorApplication.delayCall += () =>
                                {
                                    if (!_isComparing) return; // Check if cancelled
                                    _progress = (float)currentProcessed / totalItems;
                                    _progressMessage = $"Compared {currentProcessed} of {totalItems} items...";
                                    _treeView?.Reload(); // Reload to show updated status icons/text
                                    Repaint();
                                };
                            }
                        }
                    }, token)); // Pass token to Task.Run
                }

                await Task.WhenAll(comparisonTasks); // Wait for all comparison tasks
            } // End using semaphore

            // Final summary update on main thread
            EditorApplication.delayCall += () =>
            {
                if (token.IsCancellationRequested)
                {
                    _summaryMessage = $"Comparison cancelled after processing {processedCount} items.";
                }
                else
                {
                    _summaryMessage =
                        $"Comparison complete. Total: {totalItems} | Matches: {matchCount} | Mismatches: {mismatchCount} | Local Empty/No Template: {localEmptyCount} | Errors: {errorCount}";
                    _progress = 1.0f;
                    _progressMessage = "Comparison Finished.";
                }

                _treeView?.Reload(); // Final reload to ensure all data is displayed
                Repaint();
            };
        }
        catch (OperationCanceledException)
        {
            // Expected when cancellation is requested
            EditorApplication.delayCall += () =>
            {
                _summaryMessage = "Comparison cancelled.";
                Repaint();
            };
        }
        catch (Exception ex)
        {
            Debug.LogError($"[BulkWikiComparator] Unexpected error during bulk comparison: {ex}");
            EditorApplication.delayCall += () =>
            {
                _summaryMessage = $"An unexpected error occurred: {ex.Message}";
                Repaint();
            };
        }
        finally
        {
            // Ensure state is reset regardless of how the process ended
            EditorApplication.delayCall += () =>
            {
                _isComparing = false;
                _cancellationTokenSource?.Dispose();
                _cancellationTokenSource = null;
                Repaint(); // Repaint to re-enable button etc.
            };
        }
    }

    private void InitializeResultsList(List<ItemDBRecord> items)
    {
        _comparisonResults = items.Select((item, index) =>
            new ComparisonResultItem(index) // Use index for unique TreeView ID
            {
                ItemId = item.Id,
                ItemName = item.ItemName,
                Status = ComparisonStatus.Pending,
                Details = "Pending comparison...",
                LocalWikiString = item.WikiString, // Store original local string
                // Display texts will be populated after comparison
                DisplayLocalText = item.WikiString, // Initially show raw local string
                DisplayOnlineText = "<Pending>"
            }).ToList();
    }

    // --- TreeView Event Handlers ---

    private void OnSortingChanged(MultiColumnHeader multiColumnHeader)
    {
        if (_treeView == null) return;

        var sortedColumns = multiColumnHeader.state.sortedColumns;
        if (sortedColumns.Length == 0) return;

        var sortedColumnIndex = sortedColumns[0];
        var ascending = multiColumnHeader.IsSortedAscending(sortedColumnIndex);

        _treeView.SortItems(sortedColumnIndex, ascending);
        _treeView.Reload();
    }

    private void OnTreeViewSelectionChanged(IList<int> selectedIds)
    {
        if (_treeView == null || selectedIds.Count == 0)
        {
            _selectedItem = null;
        }
        else
        {
            // Find the corresponding ComparisonResultItem based on the TreeViewItem's ID
            _selectedItem = _treeView.GetItemById(selectedIds[0]); // Assuming single selection
        }

        // Clear scroll positions when selection changes
        _scrollPosLocal = Vector2.zero;
        _scrollPosOnline = Vector2.zero;
        Repaint(); // Redraw to show/hide detail view
    }
}

// --- TreeView Data Structures ---

public enum ComparisonStatus
{
    Pending,
    Match,
    Mismatch,
    LocalEmpty, // Special case: Local WikiString was empty or had no template
    Error // Fetch error, parse error, item not found etc.
}

// Represents a single row in the TreeView
public class ComparisonResultItem : TreeViewItem
{
    public string ItemId { get; set; } = "";
    public string ItemName { get; set; } = "";
    public ComparisonStatus Status { get; set; } = ComparisonStatus.Pending;
    public string Details { get; set; } = ""; // Error message or mismatch details
    public string? LocalWikiString { get; set; } // Original local string
    public string? DisplayOnlineText { get; set; } // Text to display in detail view (online)
    public string? DisplayLocalText { get; set; } // Text to display in detail view (local)


    public ComparisonResultItem(int id) : base(id, 0) // id, depth
    {
    }
}

// --- TreeView Implementation ---

public class BulkComparisonTreeView : TreeView
{
    private List<ComparisonResultItem> _resultsData; // Reference to the main list

    // Column identifiers
    enum ColumnID
    {
        Status,
        ItemID,
        ItemName,
        Details
    }

    public Action<IList<int>>? OnSelectionChangedCallback { get; set; }


    public BulkComparisonTreeView(TreeViewState state, MultiColumnHeader multiColumnHeader,
        List<ComparisonResultItem> resultsData)
        : base(state, multiColumnHeader)
    {
        _resultsData = resultsData;
        showAlternatingRowBackgrounds = true;
        showBorder = true;
        multiColumnHeader.sortingChanged += (header) =>
        {
            /* Handled by window */
        }; // Sorting logic is in the window
        Reload();
    }

    public void SetResults(List<ComparisonResultItem> resultsData)
    {
        _resultsData = resultsData;
        // Don't Reload() here, let the caller decide when to reload (e.g., after populating or after sorting)
    }

    public ComparisonResultItem? GetItemById(int id)
    {
        // Find the item in our data source that corresponds to the TreeViewItem id
        return _resultsData.FirstOrDefault(item => item.id == id);
    }


    protected override TreeViewItem BuildRoot()
    {
        var root = new TreeViewItem { id = -1, depth = -1, displayName = "Root" };
        var allItems = new List<TreeViewItem>();

        if (_resultsData != null)
        {
            foreach (var resultItem in _resultsData)
            {
                // The ComparisonResultItem itself inherits from TreeViewItem
                allItems.Add(resultItem);
            }
        }

        SetupParentsAndChildrenFromDepths(root, allItems);
        return root;
    }

    protected override IList<TreeViewItem> BuildRows(TreeViewItem root)
    {
        // If search string is active, filter the data
        if (!string.IsNullOrEmpty(searchString))
        {
            var filteredData = _resultsData
                .Where(item => DoesItemMatchSearch(item, searchString))
                .Cast<TreeViewItem>() // Cast back to base type for BuildRows
                .ToList();

            // Need to rebuild the parent/child relationship for the filtered list
            // Since it's a flat list, just return the filtered items.
            // If there was hierarchy, SetupParentsAndChildrenFromDepths would be needed here.
            return filteredData;
        }
        else
        {
            // No search, return all items from the root
            return base.BuildRows(root); // Use default BuildRows if no search
        }
    }

    private bool DoesItemMatchSearch(ComparisonResultItem item, string search)
    {
        search = search.ToLowerInvariant();
        return item.ItemId.ToLowerInvariant().Contains(search) ||
               item.ItemName.ToLowerInvariant().Contains(search) ||
               item.Status.ToString().ToLowerInvariant().Contains(search) ||
               item.Details.ToLowerInvariant().Contains(search);
    }

    protected override void RowGUI(RowGUIArgs args)
    {
        var item = args.item as ComparisonResultItem;
        if (item == null) return;

        for (int i = 0; i < args.GetNumVisibleColumns(); ++i)
        {
            Rect cellRect = args.GetCellRect(i);
            CenterRectUsingSingleLineHeight(ref cellRect); // Adjust rect vertically for text

            int column = args.GetColumn(i);

            switch ((ColumnID)column)
            {
                case ColumnID.Status:
                    Texture2D statusIcon = GetStatusIcon(item.Status);
                    if (statusIcon != null)
                    {
                        // Center the icon vertically, keep it small
                        float iconSize = EditorGUIUtility.singleLineHeight;
                        Rect iconRect = new Rect(cellRect.x + 2, cellRect.y + (cellRect.height - iconSize) / 2,
                            iconSize, iconSize);
                        GUI.DrawTexture(iconRect, statusIcon, ScaleMode.ScaleToFit);
                    }

                    // Optionally draw status text next to icon if space allows
                    // EditorGUI.LabelField(new Rect(cellRect.x + iconSize + 4, cellRect.y, cellRect.width - iconSize - 4, cellRect.height), item.Status.ToString());
                    break;

                case ColumnID.ItemID:
                    EditorGUI.LabelField(cellRect, item.ItemId);
                    break;

                case ColumnID.ItemName:
                    EditorGUI.LabelField(cellRect, item.ItemName);
                    break;

                case ColumnID.Details:
                    // Use a style that handles clipping better for potentially long text
                    EditorGUI.LabelField(cellRect, item.Details, EditorStyles.miniLabel);
                    break;
            }
        }
    }

    private Texture2D GetStatusIcon(ComparisonStatus status)
    {
        switch (status)
        {
            case ComparisonStatus.Match:
                return EditorGUIUtility.IconContent("TestPassed").image as Texture2D;
            case ComparisonStatus.Mismatch:
                return EditorGUIUtility.IconContent("TestFailed").image as Texture2D;
            case ComparisonStatus.Error:
                return EditorGUIUtility.IconContent("TestIgnored").image as Texture2D; // Or "Error" icon
            case ComparisonStatus.LocalEmpty:
                return EditorGUIUtility.IconContent("Warning").image as Texture2D; // Indicate non-standard match
            case ComparisonStatus.Pending:
                return EditorGUIUtility.IconContent("WaitSpin00").image as Texture2D; // Animated pending icon
            default:
                return null;
        }
    }

    // Handle selection changes and notify the window
    protected override void SelectionChanged(IList<int> selectedIds)
    {
        base.SelectionChanged(selectedIds);
        OnSelectionChangedCallback?.Invoke(selectedIds);
    }

    // Allow focusing the TreeView via keyboard (e.g., from search field)
    protected override void KeyEvent()
    {
        if (Event.current.keyCode == KeyCode.Return && HasSelection())
        {
            // Optional: Define action on Enter key (e.g., open item details?)
        }
        else
        {
            base.KeyEvent();
        }
    }


    // Define columns
    public static MultiColumnHeaderState CreateMultiColumnHeaderState()
    {
        var columns = new[]
        {
            new MultiColumnHeaderState.Column
            {
                headerContent =
                    new GUIContent(EditorGUIUtility.IconContent("TestPassed").image,
                        "Status"), // Use icon for header too
                contextMenuText = "Status",
                headerTextAlignment = TextAlignment.Center,
                sortedAscending = true,
                sortingArrowAlignment = TextAlignment.Right,
                width = 40, minWidth = 40, maxWidth = 60,
                autoResize = false, allowToggleVisibility = false, canSort = true
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Item ID"),
                headerTextAlignment = TextAlignment.Left,
                sortedAscending = true,
                sortingArrowAlignment = TextAlignment.Center,
                width = 150, minWidth = 100,
                autoResize = true, allowToggleVisibility = true, canSort = true
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Item Name"),
                headerTextAlignment = TextAlignment.Left,
                sortedAscending = true,
                sortingArrowAlignment = TextAlignment.Center,
                width = 200, minWidth = 100,
                autoResize = true, allowToggleVisibility = true, canSort = true
            },
            new MultiColumnHeaderState.Column
            {
                headerContent = new GUIContent("Details / Error"),
                headerTextAlignment = TextAlignment.Left,
                sortedAscending = true,
                sortingArrowAlignment = TextAlignment.Left,
                width = 350, minWidth = 150,
                autoResize = true, allowToggleVisibility = true, canSort = true
            }
        };

        // Ensure column names match enum for safety, though indices are used here
        System.Diagnostics.Debug.Assert(columns.Length == Enum.GetValues(typeof(ColumnID)).Length,
            "Number of columns defined must match ColumnID enum.");

        var state = new MultiColumnHeaderState(columns);
        return state;
    }

    // Sorting Logic
    public void SortItems(int columnIndex, bool ascending)
    {
        if (_resultsData == null || !_resultsData.Any()) return;

        Comparison<ComparisonResultItem> comparer;

        switch ((ColumnID)columnIndex)
        {
            case ColumnID.Status:
                comparer = (a, b) => a.Status.CompareTo(b.Status);
                break;
            case ColumnID.ItemID:
                comparer = (a, b) =>
                    EditorUtility.NaturalCompare(a.ItemId,
                        b.ItemId); // Natural compare for IDs like "Item1", "Item10"
                break;
            case ColumnID.ItemName:
                comparer = (a, b) => string.Compare(a.ItemName, b.ItemName, StringComparison.OrdinalIgnoreCase);
                break;
            case ColumnID.Details:
                comparer = (a, b) => string.Compare(a.Details, b.Details, StringComparison.OrdinalIgnoreCase);
                break;
            default:
                return; // Unknown column
        }

        _resultsData.Sort((a, b) => ascending ? comparer(a, b) : comparer(b, a));

        // Important: After sorting the data source, you need to tell the TreeView to rebuild its internal representation.
        Reload();
    }
}
