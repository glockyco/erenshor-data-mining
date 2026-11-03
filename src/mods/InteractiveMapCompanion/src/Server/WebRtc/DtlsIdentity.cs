using System.Security.Cryptography;
using Org.BouncyCastle.Asn1.Sec;
using Org.BouncyCastle.Asn1.X509;
using Org.BouncyCastle.Crypto;
using Org.BouncyCastle.Crypto.Generators;
using Org.BouncyCastle.Crypto.Operators;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Math;
using Org.BouncyCastle.Security;
using Org.BouncyCastle.X509;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// The self-signed ECDSA P-256 certificate the game presents in DTLS. Browsers accept it
/// because its SHA-256 fingerprint arrives with the pairing link, not through a CA.
/// </summary>
internal sealed class DtlsIdentity
{
    private DtlsIdentity(X509Certificate certificate, AsymmetricKeyParameter privateKey)
    {
        Certificate = certificate;
        PrivateKey = privateKey;
        using var sha256 = SHA256.Create();
        byte[] digest = sha256.ComputeHash(certificate.GetEncoded());
        Fingerprint = string.Join(":", digest.Select(b => b.ToString("X2")));
    }

    public X509Certificate Certificate { get; }

    public AsymmetricKeyParameter PrivateKey { get; }

    /// <summary>
    /// Upper-case hex SHA-256 digest with colons, as SDP's a=fingerprint writes it.
    /// </summary>
    public string Fingerprint { get; }

    public static DtlsIdentity Create()
    {
        var random = new SecureRandom();
        var keyGenerator = new ECKeyPairGenerator();
        keyGenerator.Init(new ECKeyGenerationParameters(SecObjectIdentifiers.SecP256r1, random));
        AsymmetricCipherKeyPair keyPair = keyGenerator.GenerateKeyPair();

        var name = new X509Name("CN=InteractiveMapCompanion");
        var generator = new X509V3CertificateGenerator();
        generator.SetSerialNumber(new BigInteger(64, random).Add(BigInteger.One));
        generator.SetIssuerDN(name);
        generator.SetSubjectDN(name);
        generator.SetNotBefore(DateTime.UtcNow.AddDays(-1));
        generator.SetNotAfter(DateTime.UtcNow.AddYears(1));
        generator.SetPublicKey(keyPair.Public);

        var signer = new Asn1SignatureFactory("SHA256WITHECDSA", keyPair.Private, random);
        return new DtlsIdentity(generator.Generate(signer), keyPair.Private);
    }
}
