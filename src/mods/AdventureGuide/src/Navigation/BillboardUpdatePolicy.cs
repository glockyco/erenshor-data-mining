namespace AdventureGuide.Navigation;

/// <summary>Camera target an active marker should face during its update.</summary>
internal enum BillboardUpdateTarget
{
    None,
    GameCamera,
    DroneCamera,
    FirstPersonCamera,
}

/// <summary>
/// Selects the camera used to billboard a marker without depending on Unity or
/// a particular loader. The result is a value type, so this is allocation-free
/// when called from <c>MarkerBillboard.Update</c>.
/// </summary>
internal static class BillboardUpdatePolicy
{
    public static BillboardUpdateTarget Select(
        bool hasPlayer,
        bool firstPersonCameraActive,
        bool droneMode
    )
    {
        if (!hasPlayer)
            return BillboardUpdateTarget.None;

        if (firstPersonCameraActive)
            return BillboardUpdateTarget.FirstPersonCamera;

        return droneMode ? BillboardUpdateTarget.DroneCamera : BillboardUpdateTarget.GameCamera;
    }
}
