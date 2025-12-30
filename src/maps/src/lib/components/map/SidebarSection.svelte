<script lang="ts">
    import type { Snippet } from 'svelte';

    interface Props {
        title: string;
        expanded?: boolean;
        children: Snippet;
    }

    let { title, expanded = $bindable(true), children }: Props = $props();

    function toggle() {
        expanded = !expanded;
    }
</script>

<div class="border-b border-zinc-700">
    <button
        type="button"
        onclick={toggle}
        class="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-zinc-400 hover:bg-zinc-700/50 hover:text-zinc-300"
    >
        <span>{title}</span>
        <svg
            class="h-4 w-4 transition-transform"
            class:rotate-180={!expanded}
            viewBox="0 0 20 20"
            fill="currentColor"
        >
            <path
                fill-rule="evenodd"
                d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
                clip-rule="evenodd"
            />
        </svg>
    </button>
    {#if expanded}
        <div class="px-3 pb-2">
            {@render children()}
        </div>
    {/if}
</div>
