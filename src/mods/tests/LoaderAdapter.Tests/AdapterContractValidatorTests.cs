using Xunit;

namespace LoaderAdapter.Tests;

public sealed class AdapterContractValidatorTests
{
    private static readonly AdapterContract Contract = new(
        "src/mods/Fixture/Fixture.csproj",
        "src/mods/Fixture/src/Plugin.BepInEx.cs",
        "BepInPlugin",
        "Awake",
        "_runtime"
    );

    [Fact]
    public void Valid_fixture_passes_all_syntax_contracts()
    {
        var diagnostics = AdapterContractValidator.Validate(Contract, ValidFixture);

        Assert.Empty(diagnostics);
    }

    [Fact]
    public void Awake_hide_flags_reordered_after_startup_fails()
    {
        const string reordered = """
            using BepInEx;
            using UnityEngine;
            [BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
            public sealed class Plugin : BaseUnityPlugin
            {
                private Runtime _runtime = new();
                private EventSource _source = new();
                private void Awake()
                {
                    _runtime.Start();
                    gameObject.hideFlags = HideFlags.HideAndDontSave;
                    _source.Changed += OnChanged;
                }
                private void OnDestroy()
                {
                    _source.Changed -= OnChanged;
                    _runtime.Stop();
                }
                private void OnChanged() { }
            }
            """;

        var diagnostics = AdapterContractValidator.Validate(Contract, reordered);

        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("awake-first-operation", StringComparison.Ordinal)
        );
        Assert.All(
            diagnostics,
            diagnostic => AssertDiagnosticNamesContractSourceAndCheck(diagnostic)
        );
    }

    [Fact]
    public void Missing_startup_invocation_fails()
    {
        const string missingStartup = """
            using BepInEx;
            using UnityEngine;
            [BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
            public sealed class Plugin : BaseUnityPlugin
            {
                private Runtime _runtime = new();
                private EventSource _source = new();
                private void Awake()
                {
                    gameObject.hideFlags = HideFlags.HideAndDontSave;
                    _source.Changed += OnChanged;
                }
                private void OnDestroy()
                {
                    _source.Changed -= OnChanged;
                    _runtime.Stop();
                }
                private void OnChanged() { }
            }
            """;

        var diagnostics = AdapterContractValidator.Validate(Contract, missingStartup);

        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("startup", StringComparison.Ordinal)
        );
    }

    [Fact]
    public void Missing_tick_invocation_fails()
    {
        var missingTick = ValidFixture.Replace("_runtime.Tick();", "", StringComparison.Ordinal);

        var diagnostics = AdapterContractValidator.Validate(Contract, missingTick);

        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("tick", StringComparison.Ordinal)
        );
    }

    [Fact]
    public void Missing_stop_invocation_fails()
    {
        var missingStop = ValidFixture.Replace("_runtime.Stop();", "", StringComparison.Ordinal);

        var diagnostics = AdapterContractValidator.Validate(Contract, missingStop);

        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("stop", StringComparison.Ordinal)
        );
    }

    [Fact]
    public void Subscription_without_unsubscription_fails()
    {
        var missingUnsubscription = ValidFixture.Replace(
            "_source.Changed -= OnChanged;",
            "",
            StringComparison.Ordinal
        );

        var diagnostics = AdapterContractValidator.Validate(Contract, missingUnsubscription);

        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("subscriptions", StringComparison.Ordinal)
        );
    }

    [Fact]
    public void Wrong_or_absent_metadata_fails()
    {
        var wrongVersion = ValidFixture.Replace(
            "PluginInfo.Version",
            "\"1.0.0\"",
            StringComparison.Ordinal
        );
        var absentMetadata = ValidFixture.Replace(
            "[BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]\n",
            "",
            StringComparison.Ordinal
        );

        var wrongDiagnostics = AdapterContractValidator.Validate(Contract, wrongVersion);
        var absentDiagnostics = AdapterContractValidator.Validate(Contract, absentMetadata);

        Assert.Contains(
            wrongDiagnostics,
            diagnostic => diagnostic.Contains("metadata-version", StringComparison.Ordinal)
        );
        Assert.Contains(
            absentDiagnostics,
            diagnostic => diagnostic.Contains("metadata", StringComparison.Ordinal)
        );
    }

    [Fact]
    public void Parameterized_start_overload_cannot_satisfy_unity_callback()
    {
        var legacyContract = Contract with { StartupMethod = "Start" };
        const string source = """
            using BepInEx;
            using UnityEngine;
            [BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
            public sealed class Plugin : BaseUnityPlugin
            {
                private Runtime _runtime = new();
                private void Awake()
                {
                    gameObject.hideFlags = HideFlags.HideAndDontSave;
                }
                private void Start() { }
                private void Start(int ignored) => _runtime.Start();
                private void OnDestroy() => _runtime.Stop();
            }
            """;

        var diagnostics = AdapterContractValidator.Validate(legacyContract, source);

        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("startup", StringComparison.Ordinal)
        );
    }

    [Fact]
    public void Deferred_lifecycle_calls_and_unsubscription_do_not_satisfy_callbacks()
    {
        const string source = """
            using BepInEx;
            using UnityEngine;
            [BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
            public sealed class Plugin : BaseUnityPlugin
            {
                private Runtime _runtime = new();
                private EventSource _source = new();
                private void Awake()
                {
                    gameObject.hideFlags = HideFlags.HideAndDontSave;
                    _source.Changed += OnChanged;
                    System.Action deferredStart = () => _runtime.Start();
                }
                private void OnDestroy()
                {
                    void DeferredStop() => _runtime.Stop();
                    System.Action deferredCleanup = () => _source.Changed -= OnChanged;
                }
                private void OnChanged() { }
            }
            """;

        var diagnostics = AdapterContractValidator.Validate(Contract, source);

        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("startup", StringComparison.Ordinal)
        );
        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("stop", StringComparison.Ordinal)
        );
        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("subscriptions", StringComparison.Ordinal)
        );
    }

    [Fact]
    public void Zero_inventory_fails_closed()
    {
        var diagnostics = AdapterContractValidator.ValidateInventory(
            new[] { Contract },
            Array.Empty<string>()
        );

        Assert.Contains(
            diagnostics,
            diagnostic =>
                diagnostic.Contains("no maintained loader adapters", StringComparison.Ordinal)
        );
        Assert.All(
            diagnostics,
            diagnostic => AssertDiagnosticNamesContractSourceAndCheck(diagnostic)
        );
    }

    [Fact]
    public void Project_compile_include_is_checked_without_source_text_matching()
    {
        const string project = """
            <Project Sdk="Microsoft.NET.Sdk">
              <ItemGroup>
                <Compile Include="src/Plugin.BepInEx.cs" />
              </ItemGroup>
            </Project>
            """;

        Assert.Empty(
            AdapterContractValidator.Validate(
                Contract with
                {
                    ProjectPath = "Fixture.csproj",
                    SourcePath = "src/Plugin.BepInEx.cs",
                },
                ValidFixture,
                project
            )
        );

        var diagnostics = AdapterContractValidator.ValidateProjectCompileInclude(
            Contract with
            {
                ProjectPath = "Fixture.csproj",
            },
            "<Project><ItemGroup><Compile Include=\"src/Other.cs\" /></ItemGroup></Project>"
        );

        Assert.Contains(
            diagnostics,
            diagnostic => diagnostic.Contains("project-compile-include", StringComparison.Ordinal)
        );
    }

    private static void AssertDiagnosticNamesContractSourceAndCheck(string diagnostic)
    {
        Assert.Contains("contract", diagnostic, StringComparison.Ordinal);
        Assert.Contains("source", diagnostic, StringComparison.Ordinal);
        Assert.Contains("check", diagnostic, StringComparison.Ordinal);
    }

    private const string ValidFixture = """
        using BepInEx;
        using UnityEngine;
        [BepInPlugin(PluginInfo.GUID, PluginInfo.Name, PluginInfo.Version)]
        public sealed class Plugin : BaseUnityPlugin
        {
            private Runtime _runtime = new();
            private EventSource _source = new();
            private void Awake()
            {
                gameObject.hideFlags = HideFlags.HideAndDontSave;
                _source.Changed += OnChanged;
                _runtime.Start();
            }
            private void Update() => _runtime.Tick();
            private void OnDestroy()
            {
                _source.Changed -= OnChanged;
                _runtime.Stop();
            }
            private void OnChanged() { }
        }
        """;
}
