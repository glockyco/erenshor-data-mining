using System.Diagnostics;
using System.Text;

namespace AdventureGuide.Diagnostics;

internal sealed class DiagnosticsCore
{
    private const int SummarySpanCount = 5;

    private readonly IncidentThresholds _incidentThresholds;
    private readonly DiagnosticEvent[] _events;
    private readonly DiagnosticSpan[] _spans;
    private readonly IncidentBundle?[] _incidents;
    private int _eventHead;
    private int _eventCount;
    private int _spanHead;
    private int _spanCount;
    private int _incidentHead;
    private int _incidentCount;
    private int _nextSpanId = 1;
    private readonly Queue<long> _recentMarkerRebuilds = new();
    private DiagnosticIncident? _lastIncident;

    public DiagnosticsCore(
        int eventCapacity,
        int spanCapacity,
        int incidentCapacity,
        IncidentThresholds incidentThresholds
    )
    {
        if (eventCapacity <= 0)
            throw new ArgumentOutOfRangeException(nameof(eventCapacity));
        if (spanCapacity <= 0)
            throw new ArgumentOutOfRangeException(nameof(spanCapacity));
        if (incidentCapacity <= 0)
            throw new ArgumentOutOfRangeException(nameof(incidentCapacity));
        _events = new DiagnosticEvent[eventCapacity];
        _spans = new DiagnosticSpan[spanCapacity];
        _incidents = new IncidentBundle?[incidentCapacity];
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

    public SpanToken BeginSpan(
        DiagnosticSpanKind kind,
        DiagnosticsContext context,
        string? primaryKey = null
    )
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
            value1
        );
        _spans[_spanHead] = span;
        _spanHead = (_spanHead + 1) % _spans.Length;
        if (_spanCount < _spans.Length)
            _spanCount++;

        if (elapsedTicks >= _incidentThresholds.FrameStallTicks)
        {
            CaptureFrameIncident(span, DiagnosticIncidentKind.FrameStall, _incidentThresholds.FrameStallTicks);
        }
        else if (elapsedTicks >= _incidentThresholds.FrameHitchTicks)
        {
            CaptureFrameIncident(span, DiagnosticIncidentKind.FrameHitch, _incidentThresholds.FrameHitchTicks);
        }
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

    public IReadOnlyList<IncidentBundle> GetRecentIncidents()
    {
        return ReadWindow(_incidents, _incidentHead, _incidentCount);
    }

    public IncidentBundle? TryGetLastIncidentBundle()
    {
        if (_incidentCount == 0)
            return null;
        int lastIndex = (_incidentHead - 1 + _incidents.Length) % _incidents.Length;
        return _incidents[lastIndex];
    }

    public IncidentBundle CaptureNow(IReadOnlyList<SnapshotEnvelope> snapshots)
    {
        var incident = new DiagnosticIncident(
            DiagnosticIncidentKind.ManualCapture,
            Stopwatch.GetTimestamp(),
            summary: "Manual capture"
        );
        _lastIncident = incident;
        return IncidentBundle.Create(incident, GetRecentEvents(), GetRecentSpans(), snapshots);
    }

    public string FormatRecentSummary()
    {
        var sb = new StringBuilder();
        sb.AppendLine(
            _lastIncident == null
                ? "Last incident: none"
                : $"Last incident: {_lastIncident.Kind} ({_lastIncident.Summary ?? "no summary"})"
        );

        var spans = GetRecentSpans();
        if (spans.Count == 0)
        {
            sb.AppendLine("Recent spans: none");
            return sb.ToString();
        }

        sb.AppendLine("Recent spans:");
        int start = Math.Max(0, spans.Count - SummarySpanCount);
        for (int i = start; i < spans.Count; i++)
        {
            var span = spans[i];
            sb.AppendLine($"  {span.Kind}: {ToMilliseconds(span.ElapsedTicks):F3} ms");
        }
        return sb.ToString();
    }

    public string FormatLastIncidentSummary()
    {
        if (_lastIncident == null)
            return "No incident captured.";
        return $"Last incident: {_lastIncident.Kind} - {_lastIncident.Summary ?? "no summary"}";
    }

    public string FormatCompactIncidentSummary()
    {
        return IncidentReportFormatter.FormatCompact(TryGetLastIncidentBundle());
    }

    public string FormatDetailedLastIncident()
    {
        var bundle = TryGetLastIncidentBundle();
        if (bundle == null)
            return "No incident captured.";
        return IncidentReportFormatter.FormatDetailed(bundle);
    }

    public string FormatAllIncidents()
    {
        var incidents = GetRecentIncidents();
        if (incidents.Count == 0)
            return "No incidents in history.";

        var sb = new StringBuilder();
        for (int i = incidents.Count - 1; i >= 0; i--)
        {
            if (sb.Length > 0)
                sb.AppendLine().AppendLine();
            sb.AppendLine($"=== Incident {i} ===");
            sb.Append(IncidentReportFormatter.FormatDetailed(incidents[i]));
        }
        return sb.ToString();
    }

    public string FormatDetailedIncidentAt(int index)
    {
        var incidents = GetRecentIncidents();
        if (incidents.Count == 0)
            return "No incidents in history.";

        // Clamp index safely
        int clampedIndex = Math.Max(0, Math.Min(index, incidents.Count - 1));
        return IncidentReportFormatter.FormatDetailed(incidents[clampedIndex]);
    }

    public string FormatIncidentListLabel(int index)
    {
        var incidents = GetRecentIncidents();
        if (index < 0 || index >= incidents.Count)
            return $"[{index}] (invalid)";
        
        var incident = incidents[index].Incident;
        return $"[{index}] {incident.Kind} - {ToMilliseconds(incident.TriggerElapsedTicks):F1} ms";
    }

    public double GetLastSpanMilliseconds(DiagnosticSpanKind kind)
    {
        var spans = GetRecentSpans();
        for (int i = spans.Count - 1; i >= 0; i--)
        {
            if (spans[i].Kind == kind)
                return ToMilliseconds(spans[i].ElapsedTicks);
        }
        return 0d;
    }

    public void ResetAll()
    {
        _eventHead = 0;
        _eventCount = 0;
        _spanHead = 0;
        _spanCount = 0;
        _incidentHead = 0;
        _incidentCount = 0;
        _recentMarkerRebuilds.Clear();
        _lastIncident = null;
    }

    private void CaptureFrameIncident(DiagnosticSpan span, DiagnosticIncidentKind kind, long thresholdTicks)
    {
        string label = string.IsNullOrEmpty(span.PrimaryKey)
            ? span.Kind.ToString()
            : $"{span.Kind} ({span.PrimaryKey})";
        var incident = new DiagnosticIncident(
            kind,
            span.EndTicks,
            summary: $"Span {label} exceeded the frame {(kind == DiagnosticIncidentKind.FrameStall ? "stall" : "hitch")} threshold.",
            triggerSpanKind: span.Kind,
            triggerPrimaryKey: span.PrimaryKey,
            triggerElapsedTicks: span.ElapsedTicks,
            thresholdTicks: thresholdTicks,
            correlationId: span.Context.CorrelationId,
            parentSpanId: span.Context.ParentSpanId
        );
        _lastIncident = incident;
        var bundle = IncidentBundle.Create(
            incident,
            CaptureRelatedEvents(span.Context.CorrelationId),
            CaptureRelatedSpans(span.Context.CorrelationId),
            Array.Empty<SnapshotEnvelope>()
        );
        AppendIncident(bundle);
    }

    private IEnumerable<DiagnosticEvent> CaptureRelatedEvents(int correlationId)
    {
        if (_eventCount == 0)
            return Array.Empty<DiagnosticEvent>();

        var events = GetRecentEvents();
        
        // If no correlation ID, use recent tail fallback
        if (correlationId == 0)
            return events.TakeLast(5);

        // Otherwise, only return events matching this specific correlation ID
        var result = new List<DiagnosticEvent>();
        foreach (var evt in events)
        {
            if (evt.Context.CorrelationId == correlationId)
                result.Add(evt);
        }
        return result;
    }

    private IEnumerable<DiagnosticSpan> CaptureRelatedSpans(int correlationId)
    {
        if (_spanCount == 0)
            return Array.Empty<DiagnosticSpan>();

        var spans = GetRecentSpans();
        
        // If no correlation ID, use recent tail fallback
        if (correlationId == 0)
            return spans.TakeLast(5);

        // Otherwise, only return spans matching this specific correlation ID
        var result = new List<DiagnosticSpan>();
        foreach (var span in spans)
        {
            if (span.Context.CorrelationId == correlationId)
                result.Add(span);
        }
        return result;
    }

    private void AppendIncident(IncidentBundle bundle)
    {
        _incidents[_incidentHead] = bundle;
        _incidentHead = (_incidentHead + 1) % _incidents.Length;
        if (_incidentCount < _incidents.Length)
            _incidentCount++;
    }

    private void DetectIncident(DiagnosticEvent evt)
    {
        if (evt.Kind != DiagnosticEventKind.MarkerRebuildRequested)
            return;

        _recentMarkerRebuilds.Enqueue(evt.TimestampTicks);
        while (
            _recentMarkerRebuilds.Count > 0
            && evt.TimestampTicks - _recentMarkerRebuilds.Peek()
                > _incidentThresholds.RebuildStormWindowTicks
        )
        {
            _recentMarkerRebuilds.Dequeue();
        }

        if (_recentMarkerRebuilds.Count >= _incidentThresholds.RebuildStormCount)
        {
            _lastIncident = new DiagnosticIncident(
                DiagnosticIncidentKind.RebuildStorm,
                evt.TimestampTicks,
                summary: "Repeated marker rebuild requests exceeded the configured window."
            );
        }
    }

    private static double ToMilliseconds(long ticks)
    {
        return ticks * 1000d / Stopwatch.Frequency;
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

    private static IReadOnlyList<IncidentBundle> ReadWindow(IncidentBundle?[] ring, int head, int count)
    {
        if (count == 0)
            return Array.Empty<IncidentBundle>();

        var result = new List<IncidentBundle>();
        int start = (head - count + ring.Length) % ring.Length;
        for (int i = 0; i < count; i++)
        {
            var item = ring[(start + i) % ring.Length];
            if (item != null)
                result.Add(item);
        }
        return result;
    }
}
