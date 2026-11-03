using System.Security.Cryptography;
using Org.BouncyCastle.Asn1.Sec;
using Org.BouncyCastle.Asn1.X509;
using Org.BouncyCastle.Crypto;
using Org.BouncyCastle.Crypto.Generators;
using Org.BouncyCastle.Crypto.Operators;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Math;
using Org.BouncyCastle.Pkcs;
using Org.BouncyCastle.Security;
using Org.BouncyCastle.X509;

namespace InteractiveMapCompanion.Server.WebRtc;

/// <summary>
/// The self-signed ECDSA P-256 certificate the game presents in DTLS. Browsers accept it
/// because its SHA-256 fingerprint arrives with the pairing link, not through a CA. It is
/// stored with the sharing settings so a paired device keeps working after a restart.
/// </summary>
internal sealed class DtlsIdentity
{
    private DtlsIdentity(X509Certificate certificate, ECPrivateKeyParameters privateKey)
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

    /// <summary>
    /// The certificate in DER.
    /// </summary>
    public byte[] CertificateDer => Certificate.GetEncoded();

    /// <summary>
    /// The private key as PKCS#8 DER.
    /// </summary>
    public byte[] PrivateKeyDer =>
        PrivateKeyInfoFactory.CreatePrivateKeyInfo(PrivateKey).GetDerEncoded();

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
        // Pairing links carry the fingerprint, so the certificate lasts as long as a pairing.
        generator.SetNotAfter(DateTime.UtcNow.AddYears(10));
        generator.SetPublicKey(keyPair.Public);

        var signer = new Asn1SignatureFactory("SHA256WITHECDSA", keyPair.Private, random);
        return new DtlsIdentity(
            generator.Generate(signer),
            (ECPrivateKeyParameters)keyPair.Private
        );
    }

    /// <summary>
    /// Restores an identity from <see cref="CertificateDer"/> and <see cref="PrivateKeyDer"/>.
    /// Returns null when the data is malformed, the certificate expired, or the key does
    /// not belong to the certificate.
    /// </summary>
    public static DtlsIdentity? FromEncoded(byte[] certificateDer, byte[] privateKeyDer)
    {
        try
        {
            X509Certificate? certificate = new X509CertificateParser().ReadCertificate(
                certificateDer
            );
            if (certificate == null || !certificate.IsValid(DateTime.UtcNow))
                return null;
            if (
                PrivateKeyFactory.CreateKey(privateKeyDer) is not ECPrivateKeyParameters privateKey
                || certificate.GetPublicKey() is not ECPublicKeyParameters publicKey
            )
                return null;

            var derived = privateKey.Parameters.G.Multiply(privateKey.D).Normalize();
            if (!derived.Equals(publicKey.Q.Normalize()))
                return null;

            return new DtlsIdentity(certificate, privateKey);
        }
        catch (Exception)
        {
            // BouncyCastle reports malformed DER through several unrelated exception types.
            // Any of them means the stored identity is unusable and a new one is generated.
            return null;
        }
    }
}
