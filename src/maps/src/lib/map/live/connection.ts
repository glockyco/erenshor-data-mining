/**
 * Connection to the InteractiveMapCompanion mod.
 *
 * The map on the game PC reaches the mod over a loopback WebSocket. Other devices reach
 * it over a WebRTC data channel described by a pairing link. Both carry the same JSON
 * messages, so the connection only swaps the transport. It reconnects until
 * `disconnect()`: each attempt goes `connecting`, then `connected` or `reconnecting`.
 */

import { browser } from '$app/environment';
import { firstMid, remoteAnswer, type PairingLink } from './pairing';
import type { ProtocolMessage, ConnectionState, SetSharingMessage } from './types';

/** The mod's WebSocket on the game PC (its default `Server.Port`) */
export const LOCAL_SERVER_URL = 'ws://localhost:18585';

/** Wait between attempts in milliseconds */
const RECONNECT_INTERVAL_MS = 2000;

/** How long a WebRTC attempt may take before it counts as failed */
const WEBRTC_CONNECT_TIMEOUT_MS = 10000;

/** How long a WebRTC connection may stay interrupted before it counts as closed */
const WEBRTC_INTERRUPTION_GRACE_MS = 5000;

/** Expected protocol version for compatibility check */
const EXPECTED_PROTOCOL_VERSION = '0.3.0';

interface TransportEvents {
    onOpen(): void;
    onMessage(data: string): void;
    /** Called once, when the transport closes or fails to open */
    onClose(): void;
}

/**
 * One attempt to reach the mod. A transport is used once: after `onClose` the
 * connection creates a new one.
 */
export interface LiveTransport {
    open(events: TransportEvents): void;
    /** Returns false when the transport is not open */
    send(data: string): boolean;
    close(): void;
}

/** Loopback WebSocket to the mod on the game PC. */
export class WebSocketTransport implements LiveTransport {
    private ws: WebSocket | null = null;
    private closed = false;

    constructor(private readonly url: string) {}

    open(events: TransportEvents): void {
        let notified = false;
        const finish = () => {
            if (notified) return;
            notified = true;
            this.ws = null;
            events.onClose();
        };

        try {
            const ws = new WebSocket(this.url);
            this.ws = ws;
            ws.onopen = () => events.onOpen();
            ws.onmessage = (event) => events.onMessage(event.data);
            ws.onclose = finish;
            // An error event is always followed by a close event.
            ws.onerror = () => {};
        } catch (e) {
            console.error('[LiveConnection] Failed to create WebSocket:', e);
            queueMicrotask(finish);
        }
    }

    send(data: string): boolean {
        if (this.closed || this.ws?.readyState !== WebSocket.OPEN) return false;
        this.ws.send(data);
        return true;
    }

    close(): void {
        this.closed = true;
        this.ws?.close();
        this.ws = null;
    }
}

/**
 * WebRTC data channel to the mod on another PC. The browser makes the offer and
 * answers it itself from the pairing link, so nothing travels to the game before the
 * connection checks.
 */
export class WebRtcTransport implements LiveTransport {
    private pc: RTCPeerConnection | null = null;
    private channel: RTCDataChannel | null = null;
    private timers: ReturnType<typeof setTimeout>[] = [];
    private finished = false;
    private events: TransportEvents | null = null;

    constructor(private readonly link: PairingLink) {}

    open(events: TransportEvents): void {
        this.events = events;
        let pc: RTCPeerConnection;
        try {
            pc = new RTCPeerConnection();
        } catch (e) {
            console.error('[LiveConnection] WebRTC is unavailable:', e);
            queueMicrotask(() => this.finish());
            return;
        }
        this.pc = pc;

        // The mod sends on stream 0 without announcing a channel.
        const channel = pc.createDataChannel('live', { negotiated: true, id: 0 });
        this.channel = channel;
        channel.onopen = () => {
            this.clearTimers();
            events.onOpen();
        };
        channel.onmessage = (event) => {
            if (typeof event.data === 'string') events.onMessage(event.data);
        };
        channel.onclose = () => this.finish();

        pc.onconnectionstatechange = () => {
            const state = pc.connectionState;
            if (state === 'failed' || state === 'closed') {
                this.finish();
            } else if (state === 'disconnected') {
                // Consent checks stopped getting answers. Give a brief hiccup a chance.
                this.timers.push(
                    setTimeout(() => {
                        if (pc.connectionState !== 'connected') this.finish();
                    }, WEBRTC_INTERRUPTION_GRACE_MS)
                );
            }
        };

        this.timers.push(
            setTimeout(() => {
                if (channel.readyState !== 'open') this.finish();
            }, WEBRTC_CONNECT_TIMEOUT_MS)
        );

        void this.negotiate(pc).catch((e) => {
            console.error('[LiveConnection] WebRTC negotiation failed:', e);
            this.finish();
        });
    }

    send(data: string): boolean {
        if (this.finished || this.channel?.readyState !== 'open') return false;
        this.channel.send(data);
        return true;
    }

    close(): void {
        this.finished = true;
        this.teardown();
    }

    private async negotiate(pc: RTCPeerConnection): Promise<void> {
        await pc.setLocalDescription(await pc.createOffer());
        const mid = firstMid(pc.localDescription?.sdp ?? '') ?? '0';
        await pc.setRemoteDescription({ type: 'answer', sdp: remoteAnswer(this.link, mid) });
    }

    private finish(): void {
        if (this.finished) return;
        this.finished = true;
        this.teardown();
        this.events?.onClose();
    }

    private teardown(): void {
        this.clearTimers();
        if (this.channel) {
            this.channel.onopen = this.channel.onmessage = this.channel.onclose = null;
            this.channel.close();
        }
        if (this.pc) {
            this.pc.onconnectionstatechange = null;
            this.pc.close();
        }
        this.channel = null;
        this.pc = null;
    }

    private clearTimers(): void {
        for (const timer of this.timers) clearTimeout(timer);
        this.timers = [];
    }
}

/**
 * Keeps one transport to the mod open, reconnecting until `disconnect()`.
 */
export class LiveConnection {
    private transport: LiveTransport | null = null;
    private createTransport: (() => LiveTransport) | null = null;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

    constructor(
        private readonly onStateChange: (state: ConnectionState) => void,
        private readonly onMessage: (message: ProtocolMessage) => void
    ) {}

    /**
     * Connects with transports from `createTransport`, replacing any earlier connection.
     */
    connect(createTransport: () => LiveTransport): void {
        if (!browser) return;
        this.stop();
        this.createTransport = createTransport;
        this.attempt();
    }

    /**
     * Closes the connection and stops reconnecting.
     */
    disconnect(): void {
        this.stop();
        this.onStateChange('disconnected');
    }

    get isEnabled(): boolean {
        return this.createTransport !== null;
    }

    /**
     * Sends a message to the mod. Returns false when not connected.
     */
    send(message: SetSharingMessage): boolean {
        return this.transport?.send(JSON.stringify(message)) ?? false;
    }

    private stop(): void {
        this.createTransport = null;
        this.cancelReconnect();
        const transport = this.transport;
        this.transport = null;
        transport?.close();
    }

    private attempt(): void {
        const createTransport = this.createTransport;
        if (!createTransport || this.transport) return;

        this.onStateChange('connecting');
        const transport = createTransport();
        this.transport = transport;
        transport.open({
            onOpen: () => {
                if (this.transport === transport) this.onStateChange('connected');
            },
            onMessage: (data) => {
                if (this.transport === transport) this.handleMessage(data);
            },
            onClose: () => {
                if (this.transport !== transport) return;
                this.transport = null;
                if (this.createTransport) {
                    this.onStateChange('reconnecting');
                    this.scheduleReconnect();
                } else {
                    this.onStateChange('disconnected');
                }
            }
        });
    }

    private handleMessage(data: string): void {
        try {
            const message = JSON.parse(data) as ProtocolMessage;

            if (
                message.type === 'handshake' &&
                message.protocolVersion !== EXPECTED_PROTOCOL_VERSION
            ) {
                console.warn(
                    `[LiveConnection] Protocol version mismatch: ` +
                        `expected ${EXPECTED_PROTOCOL_VERSION}, got ${message.protocolVersion}. ` +
                        `Continuing anyway.`
                );
            }

            this.onMessage(message);
        } catch (e) {
            console.error('[LiveConnection] Failed to parse message:', e);
        }
    }

    private scheduleReconnect(): void {
        this.cancelReconnect();
        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.attempt();
        }, RECONNECT_INTERVAL_MS);
    }

    private cancelReconnect(): void {
        if (this.reconnectTimer !== null) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
}
