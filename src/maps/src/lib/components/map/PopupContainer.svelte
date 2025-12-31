<script lang="ts">
    import X from '@lucide/svelte/icons/x';
    import Crosshair from '@lucide/svelte/icons/crosshair';
    import type { Snippet } from 'svelte';

    interface Props {
        title: string;
        subtitle: string;
        borderColorClass?: string;
        onClose: () => void;
        onFocus: () => void;
        children: Snippet;
        footer?: Snippet;
    }

    let {
        title,
        subtitle,
        borderColorClass = 'border-l-zinc-500',
        onClose,
        onFocus,
        children,
        footer
    }: Props = $props();
</script>

<div
    class="fixed right-4 top-4 z-40 w-80 max-h-[calc(100vh-2rem)] overflow-hidden
           rounded-lg border border-l-4 {borderColorClass} border-zinc-700
           bg-zinc-900/95 shadow-xl backdrop-blur flex flex-col"
>
    <!-- Header -->
    <div class="flex items-start justify-between border-b border-zinc-700 px-4 py-3 shrink-0">
        <div class="min-w-0 flex-1 pr-2">
            <div class="font-medium text-white truncate">{title}</div>
            <div class="text-xs text-zinc-400">{subtitle}</div>
        </div>
        <div class="flex gap-1 shrink-0">
            <button
                type="button"
                onclick={onFocus}
                class="rounded p-1.5 text-zinc-400 hover:bg-zinc-700 hover:text-white transition-colors"
                title="Focus on map"
            >
                <Crosshair class="h-4 w-4" />
            </button>
            <button
                type="button"
                onclick={onClose}
                class="rounded p-1.5 text-zinc-400 hover:bg-zinc-700 hover:text-white transition-colors"
                title="Close (Esc)"
            >
                <X class="h-4 w-4" />
            </button>
        </div>
    </div>

    <!-- Content -->
    <div class="overflow-y-auto flex-1 px-4 py-3">
        {@render children()}
    </div>

    <!-- Footer (optional) -->
    {#if footer}
        <div class="border-t border-zinc-700 px-4 py-2 text-xs text-zinc-500 shrink-0">
            {@render footer()}
        </div>
    {/if}
</div>
