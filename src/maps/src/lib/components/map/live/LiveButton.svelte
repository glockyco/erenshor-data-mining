<script lang="ts">
    import Radio from '@lucide/svelte/icons/radio';
    import { liveState } from '$lib/map/live';
    import { liveStatusColor } from './status';

    interface Props {
        /** A labelled pill on desktop, a round icon button among the phone controls */
        variant: 'pill' | 'round';
        open: boolean;
        onclick: () => void;
    }

    let { variant, open, onclick }: Props = $props();

    const color = $derived(liveStatusColor(liveState.mode, liveState.connectionState));
</script>

{#if variant === 'pill'}
    <button
        type="button"
        {onclick}
        aria-expanded={open}
        aria-haspopup="dialog"
        class="flex h-12 cursor-pointer items-center gap-2 rounded-full bg-zinc-800/95 px-[18px] text-sm font-semibold
               text-zinc-100 shadow-lg backdrop-blur transition-colors hover:bg-zinc-700/95"
    >
        <span class="h-2 w-2 flex-none rounded-full" style:background={color}></span>
        Live
    </button>
{:else}
    <button
        type="button"
        {onclick}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label="Live"
        title="Live"
        class="flex h-12 w-12 cursor-pointer items-center justify-center rounded-full bg-zinc-800/95
               shadow-lg backdrop-blur transition-colors hover:bg-zinc-700/95"
    >
        <Radio class="h-[22px] w-[22px]" style={`color: ${color}`} />
    </button>
{/if}
