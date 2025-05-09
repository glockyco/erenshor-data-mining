#nullable enable

public interface IAssetScanListener<T>
{
    void OnAssetFound(T asset);
    
    void OnScanStarted()
    {
        // do nothing (override in implementations)
    }

    void OnScanFinished()
    {
        // do nothing (override in implementations)
    }
}
