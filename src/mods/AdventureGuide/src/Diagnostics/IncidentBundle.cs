namespace AdventureGuide.Diagnostics;

internal sealed class IncidentBundle
{
    public IncidentBundle(
        DiagnosticIncident incident,
        IReadOnlyList<DiagnosticEvent> events,
        IReadOnlyList<DiagnosticSpan> spans,
        IReadOnlyList<SnapshotEnvelope> snapshots
    )
    {
        Incident = incident;
        Events = events;
        Spans = spans;
        Snapshots = snapshots;
    }

    public DiagnosticIncident Incident { get; }

    public IReadOnlyList<DiagnosticEvent> Events { get; }

    public IReadOnlyList<DiagnosticSpan> Spans { get; }

    public IReadOnlyList<SnapshotEnvelope> Snapshots { get; }

    public static IncidentBundle Create(
        DiagnosticIncident incident,
        IEnumerable<DiagnosticEvent> events,
        IEnumerable<DiagnosticSpan> spans,
        IEnumerable<SnapshotEnvelope> snapshots
    )
    {
        return new IncidentBundle(incident, events.ToArray(), spans.ToArray(), snapshots.ToArray());
    }
}
