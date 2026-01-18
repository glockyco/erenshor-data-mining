/**
 * WebSocket client for InteractiveMapCompanion mod communication.
 *
 * Manages connection lifecycle with automatic reconnection on disconnect.
 * Uses a simple state machine: disconnected -> connecting -> connected.
 * On unexpected disconnect, transitions to reconnecting and retries.
 */

import { browser } from '$app/environment';
import type { ProtocolMessage, ConnectionState } from './types';

/** Default WebSocket server URL (mod default port) */
const DEFAULT_SERVER_URL = 'ws://localhost:18585';

/** Fixed reconnection interval in milliseconds */
const RECONNECT_INTERVAL_MS = 2000;

/** Expected protocol version for compatibility check */
const EXPECTED_PROTOCOL_VERSION = '0.2.0';

/**
 * WebSocket connection manager for live entity data.
 *
 * Usage:
 * ```ts
 * const connection = new LiveConnection(
 *     (state) => console.log('State:', state),
 *     (message) => console.log('Message:', message)
 * );
 * connection.connect();
 * // Later...
 * connection.disconnect();
 * ```
 */
export class LiveConnection {
    private ws: WebSocket | null = null;
    private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    private readonly serverUrl: string;
    private enabled = false;

    private readonly onStateChange: (state: ConnectionState) => void;
    private readonly onMessage: (message: ProtocolMessage) => void;

    constructor(
        onStateChange: (state: ConnectionState) => void,
        onMessage: (message: ProtocolMessage) => void,
        serverUrl: string = DEFAULT_SERVER_URL
    ) {
        this.onStateChange = onStateChange;
        this.onMessage = onMessage;
        this.serverUrl = serverUrl;
    }

    /**
     * Start connection. Will automatically reconnect on disconnect.
     */
    connect(): void {
        if (!browser) return;
        if (this.enabled) return;

        this.enabled = true;
        this.attemptConnection();
    }

    /**
     * Stop connection and disable auto-reconnect.
     */
    disconnect(): void {
        this.enabled = false;
        this.cancelReconnect();

        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }

        this.onStateChange('disconnected');
    }

    /**
     * Check if connection is currently enabled.
     */
    get isEnabled(): boolean {
        return this.enabled;
    }

    private attemptConnection(): void {
        if (!this.enabled) return;
        if (this.ws) return;

        this.onStateChange('connecting');

        try {
            this.ws = new WebSocket(this.serverUrl);

            this.ws.onopen = () => {
                this.onStateChange('connected');
            };

            this.ws.onmessage = (event) => {
                this.handleMessage(event.data);
            };

            this.ws.onclose = () => {
                this.ws = null;

                if (this.enabled) {
                    this.onStateChange('reconnecting');
                    this.scheduleReconnect();
                } else {
                    this.onStateChange('disconnected');
                }
            };

            this.ws.onerror = () => {
                // Error event is always followed by close event, handle there
            };
        } catch (e) {
            console.error('[LiveConnection] Failed to create WebSocket:', e);
            this.ws = null;

            if (this.enabled) {
                this.onStateChange('reconnecting');
                this.scheduleReconnect();
            }
        }
    }

    private handleMessage(data: string): void {
        try {
            const message = JSON.parse(data) as ProtocolMessage;

            // Log protocol version mismatch on handshake (but continue)
            if (message.type === 'handshake') {
                if (message.protocolVersion !== EXPECTED_PROTOCOL_VERSION) {
                    console.warn(
                        `[LiveConnection] Protocol version mismatch: ` +
                            `expected ${EXPECTED_PROTOCOL_VERSION}, got ${message.protocolVersion}. ` +
                            `Continuing anyway.`
                    );
                }
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
            this.attemptConnection();
        }, RECONNECT_INTERVAL_MS);
    }

    private cancelReconnect(): void {
        if (this.reconnectTimer !== null) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }
}
