public interface IAssetScanListener<T>
{
    void OnAssetFound(T asset);
}
