namespace AdventureGuide.Core;

/// <summary>
/// Transfers backend disposal ownership to the constructed configuration and
/// releases exactly one owner across startup failure and repeated shutdown.
/// </summary>
internal sealed class RuntimeResourceOwnership : IDisposable
{
    private readonly IDisposable _backend;
    private IDisposable? _configuration;
    private bool _disposed;

    internal RuntimeResourceOwnership(IDisposable backend)
    {
        _backend = backend ?? throw new ArgumentNullException(nameof(backend));
    }

    internal void AdoptConfiguration(IDisposable configuration)
    {
        if (configuration == null)
            throw new ArgumentNullException(nameof(configuration));
        if (_disposed)
            throw new ObjectDisposedException(nameof(RuntimeResourceOwnership));
        if (_configuration is not null)
            throw new InvalidOperationException("Configuration ownership was already transferred.");

        _configuration = configuration;
    }

    public void Dispose()
    {
        if (_disposed)
            return;

        _disposed = true;
        if (_configuration is not null)
            _configuration.Dispose();
        else
            _backend.Dispose();
    }
}
