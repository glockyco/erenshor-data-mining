using System.Text.Json;
using Mono.Cecil;
using Xunit;

namespace ExportSurface.Tests;

public sealed class ExportSurfaceTests
{
    [Fact]
    public void PublicInstanceFields_returns_only_public_instance_fields_with_cecil_types()
    {
        using var module = ModuleDefinition.ReadModule(typeof(ExportSurfaceFixture).Assembly.Location);

        var fields = Checker.PublicInstanceFields(module, typeof(ExportSurfaceFixture).FullName!);

        Assert.Equal(2, fields.Count);
        Assert.Equal("System.Int32", fields[nameof(ExportSurfaceFixture.PublicNumber)]);
        Assert.Equal("System.String", fields[nameof(ExportSurfaceFixture.PublicText)]);
        Assert.DoesNotContain(nameof(ExportSurfaceFixture.PublicStaticNumber), fields.Keys);
        Assert.DoesNotContain("PrivateNumber", fields.Keys);
    }

    [Fact]
    public void PublicInstanceFields_throws_for_missing_type()
    {
        using var module = ModuleDefinition.ReadModule(typeof(ExportSurfaceFixture).Assembly.Location);

        var error = Assert.Throws<InvalidDataException>(() =>
            Checker.PublicInstanceFields(module, "ExportSurface.Tests.DoesNotExist"));

        Assert.Contains("in-scope type not found", error.Message);
    }

    [Fact]
    public void Diff_reports_an_absent_manifest_entry()
    {
        var findings = Diff(
            new(),
            new() { ["PublicNumber"] = "System.Int32" });

        var finding = Assert.Single(findings);
        Assert.Equal(new Finding("Fixture", "PublicNumber", "unclassified", null, "System.Int32"), finding);
    }

    [Fact]
    public void Diff_reports_a_blank_status()
    {
        var findings = Diff(
            new() { ["PublicNumber"] = Entry("System.Int32", status: "") },
            new() { ["PublicNumber"] = "System.Int32" });

        Assert.Equal("unclassified", Assert.Single(findings).Kind);
    }

    [Fact]
    public void Diff_reports_captured_without_by()
    {
        var findings = Diff(
            new() { ["PublicNumber"] = Entry("System.Int32", status: "captured") },
            new() { ["PublicNumber"] = "System.Int32" });

        Assert.Equal("unclassified", Assert.Single(findings).Kind);
    }

    [Fact]
    public void Diff_reports_ignored_without_reason()
    {
        var findings = Diff(
            new() { ["PublicNumber"] = Entry("System.Int32", status: "ignored") },
            new() { ["PublicNumber"] = "System.Int32" });

        Assert.Equal("unclassified", Assert.Single(findings).Kind);
    }

    [Fact]
    public void Diff_reports_a_retyped_field()
    {
        var findings = Diff(
            new() { ["PublicNumber"] = Entry("System.Int64", status: "captured", by: "FixtureListener") },
            new() { ["PublicNumber"] = "System.Int32" });

        Assert.Equal(
            new Finding("Fixture", "PublicNumber", "retype", "System.Int64", "System.Int32"),
            Assert.Single(findings));
    }

    [Fact]
    public void Diff_reports_a_stale_manifest_field()
    {
        var findings = Diff(
            new() { ["RemovedField"] = Entry("System.String", status: "ignored", reason: "not exported") },
            new());

        Assert.Equal(
            new Finding("Fixture", "RemovedField", "stale", "System.String", null),
            Assert.Single(findings));
    }

    [Fact]
    public void Diff_accepts_a_valid_captured_field()
    {
        var findings = Diff(
            new() { ["PublicNumber"] = Entry("System.Int32", status: "captured", by: "FixtureListener") },
            new() { ["PublicNumber"] = "System.Int32" });

        Assert.Empty(findings);
    }

    [Fact]
    public void Diff_accepts_a_valid_ignored_field()
    {
        var findings = Diff(
            new() { ["PublicNumber"] = Entry("System.Int32", status: "ignored", reason: "intentionally omitted") },
            new() { ["PublicNumber"] = "System.Int32" });

        Assert.Empty(findings);
    }

    [Fact]
    public void Diff_clean_matrix_accepts_captured_and_ignored_fields()
    {
        var findings = Diff(
            new()
            {
                ["PublicNumber"] = Entry("System.Int32", status: "captured", by: "FixtureListener"),
                ["PublicText"] = Entry("System.String", status: "ignored", reason: "not exported"),
            },
            new()
            {
                ["PublicNumber"] = "System.Int32",
                ["PublicText"] = "System.String",
            });

        Assert.Empty(findings);
    }

    [Fact]
    public void ManifestLoad_round_trips_json()
    {
        var expected = new Manifest(
            "build-123",
            ["Fixture"],
            new Dictionary<string, Dictionary<string, FieldEntry>>
            {
                ["Fixture"] = new()
                {
                    ["PublicNumber"] = Entry("System.Int32", status: "captured", by: "FixtureListener"),
                    ["PublicText"] = Entry("System.String", status: "ignored", reason: "not exported"),
                },
            });
        var path = WriteManifest(expected);

        try
        {
            var actual = Manifest.Load(path);

            Assert.Equal(expected.TracksBuild, actual.TracksBuild);
            Assert.Single(actual.Types);
            Assert.Equal("Fixture", actual.Types[0]);
            Assert.Equal(2, actual.Fields["Fixture"].Count);
            Assert.Equal(
                expected.Fields["Fixture"]["PublicNumber"],
                actual.Fields["Fixture"]["PublicNumber"]);
            Assert.Equal(
                expected.Fields["Fixture"]["PublicText"],
                actual.Fields["Fixture"]["PublicText"]);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void ManifestLoad_rejects_json_null_as_an_empty_manifest_result()
    {
        var path = WriteJson("null");

        try
        {
            var error = Assert.Throws<InvalidDataException>(() => Manifest.Load(path));
            Assert.Contains("empty manifest", error.Message);
        }
        finally
        {
            File.Delete(path);
        }
    }

    [Fact]
    public void ManifestLoad_rejects_malformed_json()
    {
        var path = WriteJson("{\"tracks_build\":");

        try
        {
            Assert.Throws<JsonException>(() => Manifest.Load(path));
        }
        finally
        {
            File.Delete(path);
        }
    }

    private static IEnumerable<Finding> Diff(
        Dictionary<string, FieldEntry> manifestFields,
        Dictionary<string, string> actualFields) =>
        Checker.Diff("Fixture", manifestFields, actualFields);

    private static FieldEntry Entry(
        string type,
        string status,
        string? by = null,
        string? reason = null) =>
        new(type, status, by, reason);

    private static string WriteManifest(Manifest manifest) =>
        WriteJson(JsonSerializer.Serialize(manifest));

    private static string WriteJson(string json)
    {
        var path = Path.Combine(Path.GetTempPath(), $"export-surface-{Guid.NewGuid():N}.json");
        File.WriteAllText(path, json);
        return path;
    }
}
