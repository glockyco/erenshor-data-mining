#nullable enable

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Debug = UnityEngine.Debug;

public sealed class AssetScanProfiler
{
    public static AssetScanProfiler Disabled { get; } = new AssetScanProfiler(false, string.Empty);

    private readonly Dictionary<string, Timing> _timings = new Dictionary<string, Timing>();
    private readonly Stopwatch _runStopwatch = Stopwatch.StartNew();

    public bool Enabled { get; }
    public string OutputPath { get; }

    public AssetScanProfiler(bool enabled, string outputPath)
    {
        Enabled = enabled;
        OutputPath = outputPath;
    }

    public void Measure(string category, string name, Action action)
    {
        if (!Enabled)
        {
            action();
            return;
        }

        long startTicks = _runStopwatch.ElapsedTicks;
        Stopwatch stopwatch = Stopwatch.StartNew();
        try
        {
            action();
        }
        finally
        {
            stopwatch.Stop();
            Add(category, name, startTicks, stopwatch.ElapsedTicks);
        }
    }

    public void Add(string category, string name, long startTicks, long elapsedTicks)
    {
        string key = category + "." + name;
        if (!_timings.TryGetValue(key, out Timing timing))
        {
            timing = new Timing(category, name);
            _timings[key] = timing;
        }

        timing.Calls++;
        timing.ElapsedTicks += elapsedTicks;
        if (elapsedTicks > timing.MaxTicks)
        {
            timing.MaxTicks = elapsedTicks;
        }
        if (timing.FirstStartTicks == 0 || startTicks < timing.FirstStartTicks)
        {
            timing.FirstStartTicks = startTicks;
        }
    }

    public void LogAndWriteSummary()
    {
        if (!Enabled)
        {
            return;
        }

        List<ProfileRow> rows = _timings.Values
            .OrderByDescending(timing => timing.ElapsedTicks)
            .Select(timing => timing.ToRow())
            .ToList();

        foreach (ProfileRow row in rows)
        {
            Debug.Log($"[EXPORT_PROFILE] {RowLabel(row)}");
            Debug.Log("[EXPORT_PROFILE_JSON] " + JsonConvert.SerializeObject(row));
        }

        if (!string.IsNullOrEmpty(OutputPath))
        {
            string? directory = Path.GetDirectoryName(OutputPath);
            if (!string.IsNullOrEmpty(directory))
            {
                Directory.CreateDirectory(directory);
            }
            File.WriteAllText(OutputPath, JsonConvert.SerializeObject(rows, Formatting.Indented));
        }
    }

    private static string RowLabel(ProfileRow row)
    {
        return $"{row.Category}.{row.Name}: {row.TotalMs:F3}ms over {row.Calls} calls avg={row.AvgMs:F3}ms max={row.MaxMs:F3}ms";
    }

    private sealed class ProfileRow
    {
        [JsonProperty("category")]
        public string Category { get; }

        [JsonProperty("name")]
        public string Name { get; }

        [JsonProperty("calls")]
        public long Calls { get; }

        [JsonProperty("total_ms")]
        public double TotalMs { get; }

        [JsonProperty("avg_ms")]
        public double AvgMs { get; }

        [JsonProperty("max_ms")]
        public double MaxMs { get; }

        [JsonProperty("first_start_ms")]
        public double FirstStartMs { get; }

        public ProfileRow(
            string category,
            string name,
            long calls,
            double totalMs,
            double avgMs,
            double maxMs,
            double firstStartMs)
        {
            Category = category;
            Name = name;
            Calls = calls;
            TotalMs = totalMs;
            AvgMs = avgMs;
            MaxMs = maxMs;
            FirstStartMs = firstStartMs;
        }
    }

    private sealed class Timing
    {
        public string Category { get; }
        public string Name { get; }
        public long Calls { get; set; }
        public long ElapsedTicks { get; set; }
        public long MaxTicks { get; set; }
        public long FirstStartTicks { get; set; }

        public Timing(string category, string name)
        {
            Category = category;
            Name = name;
        }

        public ProfileRow ToRow()
        {
            double totalMs = TicksToMilliseconds(ElapsedTicks);
            return new ProfileRow(
                Category,
                Name,
                Calls,
                totalMs,
                Calls == 0 ? 0.0 : totalMs / Calls,
                TicksToMilliseconds(MaxTicks),
                TicksToMilliseconds(FirstStartTicks)
            );
        }

        private static double TicksToMilliseconds(long ticks)
        {
            return ticks * 1000.0 / Stopwatch.Frequency;
        }
    }
}
