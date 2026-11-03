/**
 * Pairing links from the companion mod. While sharing is on, the mod shows a link such as
 * `https://erenshor.compendiums.org/map#live=192.168.1.23:18586.<ufrag>.<password>.<fingerprint>`.
 * It carries everything the browser needs to open a WebRTC data channel to the game:
 * the game PC's address and port, the ICE credentials the game answers to, and the
 * SHA-256 fingerprint of the certificate the game presents. The fragment never reaches
 * the site's server.
 */

export interface PairingLink {
    /** IPv4 address of the game PC */
    host: string;
    /** UDP port of the game's WebRTC endpoint */
    port: number;
    /** ICE username fragment of the game */
    ufrag: string;
    /** ICE password of the game */
    password: string;
    /** Lower-case hex SHA-256 certificate fingerprint, 64 characters */
    fingerprint: string;
}

const FRAGMENT_KEY = 'live=';
const IPV4 = /^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$/;
const TOKEN = /^[A-Za-z0-9]{4,256}$/;
const FINGERPRINT = /^[0-9a-f]{64}$/;

/**
 * Reads a pairing value such as `192.168.1.23:18586.ufrag.password.fingerprint`.
 * Returns null for anything that is not a complete, well-formed pairing.
 */
export function parsePairing(value: string): PairingLink | null {
    const parts = value.split('.');
    // An IPv4 address contributes four of the dot-separated parts.
    if (parts.length !== 7) return null;

    const hostAndPort = parts.slice(0, 4).join('.');
    const colon = hostAndPort.lastIndexOf(':');
    if (colon < 0) return null;

    const host = hostAndPort.slice(0, colon);
    const portText = hostAndPort.slice(colon + 1);
    const port = Number(portText);
    const [ufrag, password, fingerprint] = parts.slice(4);

    if (
        !IPV4.test(host) ||
        !/^\d{1,5}$/.test(portText) ||
        port < 1 ||
        port > 65535 ||
        !TOKEN.test(ufrag) ||
        !TOKEN.test(password) ||
        !FINGERPRINT.test(fingerprint)
    ) {
        return null;
    }

    return { host, port, ufrag, password, fingerprint };
}

/**
 * Reads the pairing from a location hash such as `#live=...`, or returns null.
 */
export function parsePairingHash(hash: string): PairingLink | null {
    const fragment = hash.startsWith('#') ? hash.slice(1) : hash;
    if (!fragment.startsWith(FRAGMENT_KEY)) return null;
    return parsePairing(decodeURIComponent(fragment.slice(FRAGMENT_KEY.length)));
}

/**
 * Writes a pairing in the form `parsePairing` reads.
 */
export function formatPairing(link: PairingLink): string {
    return `${link.host}:${link.port}.${link.ufrag}.${link.password}.${link.fingerprint}`;
}

/**
 * The game's side of the WebRTC connection as an SDP answer to the browser's offer.
 * The game is an ICE-lite agent with one host candidate and acts as the DTLS server.
 * `mid` must be the media id of the browser's data channel section.
 */
export function remoteAnswer(link: PairingLink, mid: string): string {
    const fingerprint = link.fingerprint.toUpperCase().match(/../g)!.join(':');
    return [
        'v=0',
        `o=- ${Date.now()} 2 IN IP4 ${link.host}`,
        's=-',
        't=0 0',
        `a=group:BUNDLE ${mid}`,
        'a=ice-lite',
        `m=application ${link.port} UDP/DTLS/SCTP webrtc-datachannel`,
        `c=IN IP4 ${link.host}`,
        `a=mid:${mid}`,
        `a=ice-ufrag:${link.ufrag}`,
        `a=ice-pwd:${link.password}`,
        `a=fingerprint:sha-256 ${fingerprint}`,
        'a=setup:passive',
        'a=sctp-port:5000',
        'a=max-message-size:65536',
        `a=candidate:1 1 udp 2130706431 ${link.host} ${link.port} typ host`,
        'a=end-of-candidates',
        ''
    ].join('\r\n');
}

/**
 * The media id of the first section of a local SDP description.
 */
export function firstMid(sdp: string): string | null {
    const match = /^a=mid:(\S+)/m.exec(sdp);
    return match ? match[1] : null;
}
