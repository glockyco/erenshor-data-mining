namespace AdventureGuide.Diagnostics;

internal interface IIncidentSnapshotProvider
{
    string Name { get; }

    SnapshotEnvelope CaptureSnapshot();
}
