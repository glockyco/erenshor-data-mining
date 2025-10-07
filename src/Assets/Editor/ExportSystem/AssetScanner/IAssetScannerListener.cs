#nullable enable

public interface IAssetScanListener<T>
{
    void OnScanStarted()
    {
        // do nothing (override in implementations)
    }

    void OnAssetFound(T asset)
    {
        // do nothing (override in implementations)
    }
    
    void OnScanFinished()
    {
        // do nothing (override in implementations)
    }
}
