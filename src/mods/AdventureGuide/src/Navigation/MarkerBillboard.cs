using UnityEngine;

namespace AdventureGuide.Navigation;

/// <summary>
/// Billboards a world marker to face the active game camera.
///
/// AG previously borrowed the game's <c>NamePlate</c> component for this LookAt,
/// but <c>NamePlate.Start()</c> caches <c>GetComponent&lt;TextMeshPro&gt;().color</c>
/// — a component the marker root does not have — throwing one
/// NullReferenceException per marker on game versions that cache it. This owns
/// the billboard and null-guards scenes with no live player or camera, so it is
/// safe even if a marker is briefly active outside gameplay.
/// </summary>
public sealed class MarkerBillboard : MonoBehaviour
{
    private void Update()
    {
        var pc = GameData.PlayerControl;
        if (pc == null)
            return;

        if (!pc.FPV.gameObject.activeSelf)
        {
            if (!pc.DroneMode)
                transform.LookAt(GameData.GameCamPos);
            else
                transform.LookAt(pc.DroneCam.transform);
        }
        else
        {
            transform.LookAt(GameData.CamControl.FPV.transform.position);
        }
    }
}
