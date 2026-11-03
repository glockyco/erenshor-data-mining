<script lang="ts">
    import { liveConnection, liveState } from '$lib/map/live';
    import QrCode from './QrCode.svelte';

    interface Props {
        isDesktop: boolean;
        /** Display name of the zone the character is in */
        zoneName: string | null;
        follow: boolean;
        onFollowChange: (follow: boolean) => void;
        keepScreenOn: boolean;
        onKeepScreenOnChange: (keepScreenOn: boolean) => void;
    }

    let { isDesktop, zoneName, follow, onFollowChange, keepScreenOn, onKeepScreenOnChange }: Props =
        $props();

    /** How long a device or a sharing PC waits before the panel says what to check */
    const HINT_DELAY_MS = 20000;

    const connected = $derived(liveState.connectionState === 'connected');
    const playerName = $derived(liveState.player?.name ?? null);
    const sharing = $derived(liveState.sharing);

    // The waits are timed in the store, so the hints show however long the panel was closed.
    let now = $state(Date.now());
    $effect(() => {
        if (liveState.waitingSince === null && liveState.sharingIdleSince === null) return;
        now = Date.now();
        const timer = setInterval(() => (now = Date.now()), 1000);
        return () => clearInterval(timer);
    });
    const pairedWaitTooLong = $derived(
        liveState.mode === 'paired' &&
            liveState.waitingSince !== null &&
            now - liveState.waitingSince >= HINT_DELAY_MS
    );
    const sharingIdleTooLong = $derived(
        liveState.sharingIdleSince !== null && now - liveState.sharingIdleSince >= HINT_DELAY_MS
    );

    function devicesText(viewers: number): string {
        if (viewers === 0) return 'No device connected yet';
        return viewers === 1 ? '1 device connected' : `${viewers} devices connected`;
    }
</script>

{#snippet checkbox(checked: boolean, label: string, onchange: (checked: boolean) => void)}
    <label class="flex cursor-pointer items-center gap-2 text-[13px] text-zinc-200">
        <input
            type="checkbox"
            {checked}
            onchange={(e) => onchange(e.currentTarget.checked)}
            class="sr-only"
        />
        <span
            class="flex h-4 w-4 flex-none items-center justify-center rounded border transition-colors"
            class:bg-zinc-600={!checked}
            class:border-zinc-500={!checked}
            class:bg-cyan-500={checked}
            class:border-cyan-500={checked}
        >
            {#if checked}
                <svg class="h-3 w-3 text-white" viewBox="0 0 12 12" fill="none" stroke="currentColor">
                    <path
                        d="M2 6l3 3 5-6"
                        stroke-width="2"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                    />
                </svg>
            {/if}
        </span>
        {label}
    </label>
{/snippet}

<!-- The title of a connection with the action that ends it beside it -->
{#snippet statusRow(title: string, live: boolean, actionLabel: string, action: () => void)}
    <div class="flex items-start justify-between gap-3">
        <div class="flex min-w-0 items-center gap-2 text-sm font-semibold text-zinc-100">
            {#if live}
                <span class="h-2 w-2 flex-none rounded-full bg-lime-400"></span>
            {/if}
            <span>{title}</span>
        </div>
        <button
            type="button"
            onclick={action}
            class="flex-none cursor-pointer text-[13px] text-zinc-400 underline-offset-2 transition-colors hover:text-zinc-100 hover:underline"
        >
            {actionLabel}
        </button>
    </div>
{/snippet}

{#snippet installNote(text: string)}
    <p class="mt-3.5 text-[13px] leading-normal text-zinc-400">
        {text}
        <a href="/mod" class="text-purple-300 underline hover:text-purple-200">Install guide</a>
    </p>
{/snippet}

{#snippet hint(text: string)}
    <p class="mt-2.5 text-[13px] leading-normal text-zinc-400">{text}</p>
{/snippet}

<!-- The name of a control the text refers to, in bold as UI style guides mark it -->
{#snippet control(name: string)}
    <b class="font-semibold text-zinc-200">{name}</b>
{/snippet}

<div class="text-zinc-300" data-testid="live-panel">
    {#if liveState.mode === 'off'}
        <video
            autoplay
            muted
            loop
            playsinline
            src="/world-map-companion.mp4"
            class="mb-3 block aspect-video w-full rounded-lg bg-zinc-900 object-cover"
        ></video>
        {#if isDesktop}
            <p class="text-sm leading-normal text-zinc-300">
                See your character, party and enemies move on the map while you play.
            </p>
            <button
                type="button"
                onclick={() => liveConnection.connectLocal()}
                class="mt-3 w-full cursor-pointer rounded-md bg-purple-600 px-3 py-2 text-sm font-semibold text-white transition-colors hover:bg-purple-700"
            >
                Connect to Erenshor on this PC
            </button>
            <p class="mt-2 text-[13px] leading-normal text-zinc-400">
                Your browser then asks for access to apps on this device. Allow it so the map can
                reach the game.
            </p>
            <div class="my-3.5 h-px bg-zinc-700"></div>
            <p class="text-[13px] font-semibold text-zinc-100">Game on another PC?</p>
            <p class="mt-1 text-[13px] leading-normal text-zinc-400">
                Open {@render control('Live')} on that PC and choose {@render control(
                    'Show on another device'
                )}. It shows the address to open here.
            </p>
            {@render installNote('Live needs the Interactive Map Companion mod.')}
        {:else}
            <p class="text-base font-semibold text-zinc-100">Show your game on this phone</p>
            <p class="mt-1.5 text-sm leading-normal text-zinc-400">
                On your game PC, open {@render control('Live')} and choose {@render control(
                    'Show on another device'
                )}. Scan the code it shows with this phone's camera. Both need to be on the same
                Wi-Fi.
            </p>
            {@render installNote('Your game PC needs the Interactive Map Companion mod.')}
        {/if}
    {:else if liveState.mode === 'paired'}
        {#if connected}
            {@render statusRow(
                playerName && zoneName ? `${playerName} in ${zoneName}` : 'Connected to Erenshor',
                true,
                'Disconnect',
                () => liveConnection.disconnect()
            )}
            <div class="mt-2.5 space-y-2">
                {@render checkbox(
                    follow,
                    playerName ? `Follow ${playerName}` : 'Follow your character',
                    onFollowChange
                )}
                {@render checkbox(keepScreenOn, 'Keep the screen on', onKeepScreenOnChange)}
            </div>
        {:else}
            {@render statusRow(
                `Connecting to Erenshor at ${liveState.pairing?.host ?? ''}`,
                false,
                'Disconnect',
                () => liveConnection.disconnect()
            )}
            {#if pairedWaitTooLong}
                <p class="mt-2.5 text-[13px] leading-normal text-zinc-400">
                    Check that the game is running with {@render control('Show on another device')}
                    turned on, that both devices are on the same network, and that Windows lets Erenshor
                    use private networks.
                </p>
            {/if}
        {/if}
    {:else if connected}
        {@render statusRow(
            playerName && zoneName ? `${playerName} in ${zoneName}` : 'Connected to Erenshor',
            true,
            'Turn off Live',
            () => liveConnection.disconnect()
        )}
        <div class="mt-2.5">
            {@render checkbox(
                follow,
                playerName ? `Follow ${playerName}` : 'Follow your character',
                onFollowChange
            )}
        </div>
        <div class="my-3.5 h-px bg-zinc-700"></div>
        <p class="text-[13px] font-semibold text-zinc-100">Other devices</p>
        {#if !sharing}
            {@render hint(
                'Update the Interactive Map Companion mod to show the map on other devices.'
            )}
        {:else if sharing.enabled}
            {#if sharing.link && sharing.address}
                <div class="mt-2 flex items-center gap-3">
                    <QrCode value={sharing.link} size={112} label="Pairing code" />
                    <p class="text-[13px] leading-normal text-zinc-400">
                        Scan with a phone camera to open the map there.
                    </p>
                </div>
                <p class="mt-2.5 text-[13px] text-zinc-400">On a PC on the same network, open</p>
                <p class="font-mono text-sm font-semibold text-zinc-100" data-testid="live-address">
                    {sharing.address}
                </p>
            {:else}
                {@render hint('This PC has no network address another device can reach.')}
            {/if}
            {#if sharingIdleTooLong}
                {@render hint(
                    'A device can connect only from the same network as this PC, and only once Windows lets Erenshor use private networks.'
                )}
            {/if}
            <div class="mt-3.5 flex items-center justify-between gap-3">
                <span class="text-[13px] text-zinc-400">{devicesText(sharing.viewers)}</span>
                <button
                    type="button"
                    onclick={() => liveConnection.setSharing(false)}
                    class="cursor-pointer rounded-md border border-zinc-600 px-3 py-1.5 text-[13px] text-zinc-200 transition-colors hover:bg-zinc-700"
                >
                    Stop sharing
                </button>
            </div>
        {:else}
            {#if sharing.error === 'portUnavailable'}
                <p class="mt-1.5 text-[13px] leading-normal text-red-300">
                    Another program uses port {sharing.port}, so other devices can't connect.
                </p>
            {/if}
            <button
                type="button"
                onclick={() => liveConnection.setSharing(true)}
                class="mt-2 w-full cursor-pointer rounded-md bg-zinc-700 px-3 py-2 text-sm font-semibold text-zinc-100 transition-colors hover:bg-zinc-600"
            >
                Show on another device
            </button>
        {/if}
    {:else}
        {@render statusRow('Waiting for Erenshor on this PC', false, 'Turn off Live', () =>
            liveConnection.disconnect()
        )}
        {@render hint(
            'Start the game with the Interactive Map Companion mod. If your browser asks for access to apps on this device, allow it.'
        )}
    {/if}
</div>
