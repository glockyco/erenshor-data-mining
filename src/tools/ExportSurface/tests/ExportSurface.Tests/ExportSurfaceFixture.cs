namespace ExportSurface.Tests;

public sealed class ExportSurfaceFixture
{
    public int PublicNumber;
    public string PublicText = string.Empty;
    private decimal PrivateNumber = 1m;
    public static int PublicStaticNumber;

    public decimal ReadPrivateNumber() => PrivateNumber;
}
