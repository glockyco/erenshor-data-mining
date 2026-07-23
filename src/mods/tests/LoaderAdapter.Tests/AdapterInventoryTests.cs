using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Xunit;

namespace LoaderAdapter.Tests;

public sealed class AdapterInventoryTests
{
    [Fact]
    public void InventoryMatchesEveryMaintainedAdapterSource()
    {
        var repositoryRoot = AdapterContractInventory.FindRepositoryRoot();
        var discovered = AdapterContractInventory.DiscoverAdapterSources(repositoryRoot);
        var diagnostics = AdapterContractValidator.ValidateInventory(
            AdapterContractInventory.Contracts,
            discovered
        );

        Assert.Equal(
            AdapterContractInventory.ExpectedAdapterCount,
            AdapterContractInventory.Contracts.Count
        );
        Assert.True(
            diagnostics.Count == 0,
            $"Loader adapter inventory diagnostics:\n{string.Join(Environment.NewLine, diagnostics)}"
        );
        Assert.Equal(
            AdapterContractInventory
                .Contracts.Select(contract => contract.SourcePath)
                .OrderBy(path => path, StringComparer.Ordinal),
            discovered
        );
    }

    [Fact]
    public void EveryAdapterSourceAndProjectCompileIncludeSatisfiesItsContract()
    {
        var repositoryRoot = AdapterContractInventory.FindRepositoryRoot();
        var failures = new List<string>();

        foreach (var contract in AdapterContractInventory.Contracts)
        {
            var sourcePath = Path.Combine(
                repositoryRoot,
                contract.SourcePath.Replace('/', Path.DirectorySeparatorChar)
            );
            var projectPath = Path.Combine(
                repositoryRoot,
                contract.ProjectPath.Replace('/', Path.DirectorySeparatorChar)
            );
            var source = File.ReadAllText(sourcePath);
            var projectXml = File.ReadAllText(projectPath);

            foreach (var diagnostic in AdapterContractValidator.Validate(contract, source))
                failures.Add($"{contract.SourcePath}: {diagnostic}");

            foreach (
                var diagnostic in AdapterContractValidator.ValidateProjectCompileInclude(
                    contract,
                    projectXml
                )
            )
                failures.Add($"{contract.SourcePath}: {diagnostic}");
        }

        Assert.True(
            failures.Count == 0,
            $"Loader adapter contract failures:\n{string.Join(Environment.NewLine, failures)}"
        );
    }

    [Fact]
    public void ReorderedStartupOperationFailsTheSemanticContract()
    {
        var repositoryRoot = AdapterContractInventory.FindRepositoryRoot();
        var contract = AdapterContractInventory.Contracts[0];
        var sourcePath = Path.Combine(
            repositoryRoot,
            contract.SourcePath.Replace('/', Path.DirectorySeparatorChar)
        );
        var source = File.ReadAllText(sourcePath);
        const string hideFlagsAssignment = "gameObject.hideFlags = HideFlags.HideAndDontSave;";
        var mutatedSource = source.Replace(
            hideFlagsAssignment,
            "var operationBeforeHideFlags = true;\n        " + hideFlagsAssignment,
            StringComparison.Ordinal
        );

        Assert.NotEqual(source, mutatedSource);
        var diagnostics = AdapterContractValidator.Validate(contract, mutatedSource);

        Assert.NotEmpty(diagnostics);
    }

    [Fact]
    public void EmptyDiscoveredAdapterSetFailsInventoryValidation()
    {
        var diagnostics = AdapterContractValidator.ValidateInventory(
            AdapterContractInventory.Contracts,
            Array.Empty<string>()
        );

        Assert.NotEmpty(diagnostics);
    }
}
