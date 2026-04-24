using System.Diagnostics;
using System.Text;

namespace AdventureGuide.Diagnostics;

internal static class IncidentReportFormatter
{
    public static string FormatCompact(IncidentBundle? bundle)
    {
        if (bundle == null)
            return "Last incident: none";

        var sb = new StringBuilder();
        sb.Append("Last incident: ");
        sb.Append(bundle.Incident.Kind);
        if (bundle.Incident.TriggerSpanKind != null)
        {
            sb.Append(" (");
            sb.Append(bundle.Incident.TriggerSpanKind);
            if (!string.IsNullOrEmpty(bundle.Incident.TriggerPrimaryKey))
            {
                sb.Append(": ");
                sb.Append(bundle.Incident.TriggerPrimaryKey);
            }
            sb.Append(") ");
            sb.Append(FormatMilliseconds(bundle.Incident.TriggerElapsedTicks));
            sb.Append(" / ");
            sb.Append(FormatMilliseconds(bundle.Incident.ThresholdTicks));
        }
        return sb.ToString();
    }

    public static string FormatDetailed(IncidentBundle bundle)
    {
        var sb = new StringBuilder();
        sb.AppendLine($"Kind: {bundle.Incident.Kind}");
        sb.AppendLine($"Summary: {bundle.Incident.Summary}");
        sb.AppendLine($"Trigger: {bundle.Incident.TriggerSpanKind} ({bundle.Incident.TriggerPrimaryKey ?? "none"})");
        sb.AppendLine($"Duration: {FormatMilliseconds(bundle.Incident.TriggerElapsedTicks)}");
        sb.AppendLine($"Threshold: {FormatMilliseconds(bundle.Incident.ThresholdTicks)}");
        sb.AppendLine($"Correlation: {bundle.Incident.CorrelationId}");

        if (bundle.Spans.Count > 0)
        {
            sb.AppendLine("Related spans:");
            foreach (var span in bundle.Spans)
            {
                sb.Append($"  {span.Kind}: {FormatMilliseconds(span.ElapsedTicks)}");
                var metrics = DescribeSpanMetrics(span);
                if (!string.IsNullOrEmpty(metrics))
                    sb.Append(metrics);
                sb.AppendLine();
            }
        }
        else
        {
            sb.AppendLine("Related spans: none");
        }

        return sb.ToString();
    }

    private static string DescribeSpanMetrics(DiagnosticSpan span) =>
        span.Kind switch
        {
            DiagnosticSpanKind.SpecTreeProjectRoot =>
                $" projected nodes={span.Value0}, cycle prunes={span.Value1}",
            DiagnosticSpanKind.SpecTreeExpandNode =>
                $" immediate children={span.Value0}, drawn descendants={span.Value1}",
            DiagnosticSpanKind.NavSelectorCollectKeys =>
                $" quest keys={span.Value0}",
            DiagnosticSpanKind.NavSelectorBatchResolve =>
                $" quest keys={span.Value0}, resolved targets={span.Value1}",
            _ => string.Empty,
        };

    private static string FormatMilliseconds(long ticks)
    {
        var ms = ticks * 1000.0 / Stopwatch.Frequency;
        return $"{ms:F3} ms";
    }
}
