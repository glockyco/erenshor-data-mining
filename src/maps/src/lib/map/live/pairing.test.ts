import { describe, expect, it } from 'vitest';
import { firstMid, formatPairing, parsePairing, parsePairingHash, remoteAnswer } from './pairing';

const FINGERPRINT = 'aa4c4f5ddbc5e6906e039b321dace699eb9b1308dac992891f412ebc78ec55c5';
const UFRAG = 'testufrag';
const PASSWORD = 'testpasswordtestpassword';
const VALUE = `192.168.0.163:18586.${UFRAG}.${PASSWORD}.${FINGERPRINT}`;

describe('parsePairingHash', () => {
    it('reads the link the mod shows', () => {
        expect(parsePairingHash(`#live=${VALUE}`)).toEqual({
            host: '192.168.0.163',
            port: 18586,
            ufrag: UFRAG,
            password: PASSWORD,
            fingerprint: FINGERPRINT
        });
    });

    it('reads a link whose fragment a browser percent-encoded', () => {
        expect(parsePairingHash(`#live=${VALUE.replace(':', '%3A')}`)?.port).toBe(18586);
    });

    it('ignores other fragments', () => {
        expect(parsePairingHash('')).toBeNull();
        expect(parsePairingHash('#sel=zone:azure')).toBeNull();
        expect(parsePairingHash(`#${VALUE}`)).toBeNull();
    });
});

describe('parsePairing', () => {
    it.each([
        ['a missing fingerprint', `192.168.0.163:18586.${UFRAG}.${PASSWORD}`],
        ['an extra part', `${VALUE}.extra`],
        ['a host name', `gamepc.lan.x.y:18586.${UFRAG}.${PASSWORD}.${FINGERPRINT}`],
        ['an address out of range', VALUE.replace('192.168', '256.168')],
        ['port 0', VALUE.replace(':18586', ':0')],
        ['a port above 65535', VALUE.replace(':18586', ':70000')],
        ['a missing port', VALUE.replace(':18586', '')],
        ['a short fingerprint', VALUE.slice(0, -2)],
        ['an upper-case fingerprint', VALUE.replace(FINGERPRINT, FINGERPRINT.toUpperCase())],
        ['a password with symbols', VALUE.replace(PASSWORD, 'testpass+word/testpass')]
    ])('rejects %s', (_, value) => {
        expect(parsePairing(value)).toBeNull();
    });

    it('reads what it writes', () => {
        const pairing = parsePairing(VALUE)!;
        expect(parsePairing(formatPairing(pairing))).toEqual(pairing);
    });
});

describe('remoteAnswer', () => {
    const pairing = parsePairing(VALUE)!;
    const lines = remoteAnswer(pairing, '0').split('\r\n');

    it('describes the game as an ICE-lite DTLS server at the linked address', () => {
        expect(lines).toContain('a=ice-lite');
        expect(lines).toContain('a=setup:passive');
        expect(lines).toContain(`a=ice-ufrag:${UFRAG}`);
        expect(lines).toContain(`a=ice-pwd:${PASSWORD}`);
        expect(lines).toContain('a=candidate:1 1 udp 2130706431 192.168.0.163 18586 typ host');
        expect(lines).toContain('m=application 18586 UDP/DTLS/SCTP webrtc-datachannel');
    });

    it('writes the fingerprint as SDP expects it', () => {
        expect(lines).toContain(
            'a=fingerprint:sha-256 AA:4C:4F:5D:DB:C5:E6:90:6E:03:9B:32:1D:AC:E6:99:EB:9B:13:08:DA:C9:92:89:1F:41:2E:BC:78:EC:55:C5'
        );
    });

    it("answers the browser's media section", () => {
        const answer = remoteAnswer(pairing, 'data');
        expect(answer).toContain('a=mid:data\r\n');
        expect(answer).toContain('a=group:BUNDLE data\r\n');
    });
});

describe('firstMid', () => {
    it('finds the media id of an offer', () => {
        expect(firstMid('v=0\r\nm=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\na=mid:0\r\n')).toBe('0');
        expect(firstMid('v=0\r\n')).toBeNull();
    });
});
