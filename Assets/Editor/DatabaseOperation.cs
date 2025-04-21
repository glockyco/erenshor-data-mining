using UnityEditor;

public class DatabaseOperation
{
    public const string DB_PATH = "../Erenshor.sqlite";
    public static bool _cancelRequested = false;
    public static EditorApplication.CallbackFunction _currentUpdateDelegate = null;

    // Delegate for progress reporting
    public delegate void ProgressCallback(float progress, string status);

    // Method to request cancellation of ongoing operations
    public static void CancelOperation()
    {
        _cancelRequested = true;
    }

    // Method to reset cancellation flag
    public static void ResetCancelFlag()
    {
        _cancelRequested = false;
    }

    // Clean up any active delegates
    public static void CleanupDelegate()
    {
        if (_currentUpdateDelegate != null)
        {
            EditorApplication.update -= _currentUpdateDelegate;
            _currentUpdateDelegate = null;
        }
    }

    // Start an async operation
    public static void StartAsyncOperation(EditorApplication.CallbackFunction updateDelegate)
    {
        CleanupDelegate();
        _currentUpdateDelegate = updateDelegate;
        EditorApplication.update += _currentUpdateDelegate;
    }
}