#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using SQLite;

public sealed class WeatherTrendListener : IAssetScanListener<WeatherTrend>
{
    private readonly SQLiteConnection _db;
    private readonly List<WeatherTrendRecord> _records = new();

    public WeatherTrendListener(SQLiteConnection db) => _db = db;

    public void OnScanFinished()
    {
        _db.CreateTable<WeatherTrendRecord>();
        _db.RunInTransaction(() =>
        {
            _db.DeleteAll<WeatherTrendRecord>();
            _db.InsertAll(_records);
        });
        _records.Clear();
    }

    public void OnAssetFound(WeatherTrend asset)
    {
        var scene = asset.gameObject.scene;
        if (!scene.IsValid() || string.IsNullOrEmpty(scene.name))
            return;
        _records.Add(
            new WeatherTrendRecord
            {
                StableKey =
                    ActivationTargetResolver.ObjectKey(asset.gameObject)
                    + ":script:WeatherTrend:"
                    + Array
                        .IndexOf(asset.GetComponents<WeatherTrend>(), asset)
                        .ToString(CultureInfo.InvariantCulture),
                Scene = scene.name,
                IsEnabled = asset.isActiveAndEnabled,
                MaxNaturalCloudy = asset.MaxNaturalCloudy,
                MaxNaturalRainy = asset.MaxNaturalRainy,
            }
        );
    }
}
