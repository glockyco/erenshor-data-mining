using System.Security.Cryptography;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// What a pairing link proves: the ICE username fragment and password a browser must use
/// in its connectivity checks, and the certificate whose fingerprint it expects in DTLS.
/// The config stores it as one line so a paired device keeps working after a restart.
/// </summary>
internal sealed class SharingIdentity
{
    private const string FormatVersion = "1";
    private const string TokenAlphabet =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

    private SharingIdentity(string iceUfrag, string icePassword, DtlsIdentity dtls)
    {
        IceUfrag = iceUfrag;
        IcePassword = icePassword;
        Dtls = dtls;
    }

    public string IceUfrag { get; }

    public string IcePassword { get; }

    public DtlsIdentity Dtls { get; }

    /// <summary>
    /// The certificate fingerprint as lower-case hex without separators, as the pairing
    /// link carries it.
    /// </summary>
    public string FingerprintHex => Dtls.Fingerprint.Replace(":", "").ToLowerInvariant();

    public static SharingIdentity Create() =>
        new(RandomToken(8), RandomToken(24), DtlsIdentity.Create());

    /// <summary>
    /// Restores an identity written by <see cref="Serialize"/>. Returns null for an empty
    /// or unusable value, which the caller replaces with a new identity.
    /// </summary>
    public static SharingIdentity? Parse(string? value)
    {
        if (string.IsNullOrEmpty(value))
            return null;

        string[] parts = value!.Split('.');
        if (
            parts.Length != 5
            || parts[0] != FormatVersion
            || !IsToken(parts[1])
            || !IsToken(parts[2])
        )
            return null;

        byte[] certificate;
        byte[] privateKey;
        try
        {
            certificate = Convert.FromBase64String(parts[3]);
            privateKey = Convert.FromBase64String(parts[4]);
        }
        catch (FormatException)
        {
            return null;
        }

        DtlsIdentity? dtls = DtlsIdentity.FromEncoded(certificate, privateKey);
        return dtls == null ? null : new SharingIdentity(parts[1], parts[2], dtls);
    }

    public string Serialize() =>
        string.Join(
            ".",
            FormatVersion,
            IceUfrag,
            IcePassword,
            Convert.ToBase64String(Dtls.CertificateDer),
            Convert.ToBase64String(Dtls.PrivateKeyDer)
        );

    private static bool IsToken(string value) =>
        value.Length > 0 && value.All(c => TokenAlphabet.IndexOf(c) >= 0);

    private static string RandomToken(int length)
    {
        // Rejection sampling keeps every character equally likely.
        var chars = new char[length];
        var buffer = new byte[1];
        using var rng = RandomNumberGenerator.Create();
        int limit = 256 - 256 % TokenAlphabet.Length;
        for (int i = 0; i < length; )
        {
            rng.GetBytes(buffer);
            if (buffer[0] >= limit)
                continue;
            chars[i++] = TokenAlphabet[buffer[0] % TokenAlphabet.Length];
        }
        return new string(chars);
    }
}
