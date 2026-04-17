using System.Diagnostics;

namespace AdventureGuide.Diagnostics;

internal sealed class DiagnosticsCore
{
    private readonly IncidentThresholds _incidentThresholds;
    private readonly DiagnosticEvent[] _events;
    private readonly DiagnosticSpan[] _spans;
    private int _eventHead;
    private int _eventCount;
    private int _spanHead;
    private int _spanCount;
    private int _nextSpanId = 1;
    private readonly Queue<long> _recentMarkerRebuilds = new();
    private DiagnosticIncident? _lastIncident;

    public DiagnosticsCore(int eventCapacity, int spanCapacity, IncidentThresholds incidentThresholds)
    {
        if (eventCapacity <= 0)
            throw new ArgumentOutOfRangeException(nameof(eventCapacity));
        if (spanCapacity <= 0)
            throw new ArgumentOutOfRangeException(nameof(spanCapacity));
        _events = new DiagnosticEvent[eventCapacity];
        _spans = new DiagnosticSpan[spanCapacity];
        _incidentThresholds = incidentThresholds;
    }

    public void RecordEvent(DiagnosticEvent evt)
    {
        _events[_eventHead] = evt;
        _eventHead = (_eventHead + 1) % _events.Length;
        if (_eventCount < _events.Length)
            _eventCount++;

        DetectIncident(evt);
    }

    public SpanToken BeginSpan(DiagnosticSpanKind kind, DiagnosticsContext context, string? primaryKey = null)
    {
        return new SpanToken(_nextSpanId++, kind, context, Stopwatch.GetTimestamp(), primaryKey);
    }

    public void EndSpan(SpanToken token, long elapsedTicks, int value0 = 0, int value1 = 0)
    {
        var span = new DiagnosticSpan(
            token.Kind,
            token.Context,
            token.StartTicks,
            token.StartTicks + elapsedTicks,
            token.PrimaryKey,
            value0,
            value1);
        _spans[_spanHead] = span;
        _spanHead = (_spanHead + 1) % _spans.Length;
        if (_spanCount < _spans.Length)
            _spanCount++;

        if (elapsedTicks >= _incidentThresholds.FrameStallTicks)
            _lastIncident = new DiagnosticIncident(DiagnosticIncidentKind.FrameStall, span.EndTicks);
    }

    public IReadOnlyList<DiagnosticEvent> GetRecentEvents()
    {
        return ReadWindow(_events, _eventHead, _eventCount);
    }

    public IReadOnlyList<DiagnosticSpan> GetRecentSpans()
    {
        return ReadWindow(_spans, _spanHead, _spanCount);
    }

    public DiagnosticIncident? TryGetLastIncident()
    {
        return _lastIncident;
    }

    public IncidentBundle CaptureNow(IReadOnlyList<SnapshotEnvelope> snapshots)
    {
        var incident = new DiagnosticIncident(
            DiagnosticIncidentKind.ManualCapture,
            Stopwatch.GetTimestamp(),
            summary: "Manual capture");
        _lastIncident = incident;
        return IncidentBundle.Create(incident, GetRecentEvents(), GetRecentSpans(), snapshots);
    }

    private void DetectIncident(DiagnosticEvent evt)
    {
        if (evt.Kind != DiagnosticEventKind.MarkerRebuildRequested)
            return;

        _recentMarkerRebuilds.Enqueue(evt.TimestampTicks);
        while (_recentMarkerRebuilds.Count > 0
            && evt.TimestampTicks - _recentMarkerRebuilds.Peek() > _incidentThresholds.RebuildStormWindowTicks)
        {
            _recentMarkerRebuilds.Dequeue();
        }

        if (_recentMarkerRebuilds.Count >= _incidentThresholds.RebuildStormCount)
        {
            _lastIncident = new DiagnosticIncident(
                DiagnosticIncidentKind.RebuildStorm,
                evt.TimestampTicks,
                summary: "Repeated marker rebuild requests exceeded the configured window.");
        }
    }

    private static IReadOnlyList<T> ReadWindow<T>(T[] ring, int head, int count)
    {
        if (count == 0)
            return Array.Empty<T>();

        var result = new T[count];
        int start = (head - count + ring.Length) % ring.Length;
        for (int i = 0; i < count; i++)
            result[i] = ring[(start + i) % ring.Length];
        return result;
    }
}
