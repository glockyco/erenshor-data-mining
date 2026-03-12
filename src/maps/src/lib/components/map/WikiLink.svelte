<script lang="ts">
    import ExternalLink from '@lucide/svelte/icons/external-link';

    interface Props {
        pageName: string | null;
    }

    let { pageName }: Props = $props();

    const url = $derived(
        pageName ? `https://erenshor.wiki.gg/wiki/${encodeURIComponent(pageName)}` : null
    );
</script>

{#if url}
    <a
        href={url}
        class="flex items-center gap-1 text-xs text-zinc-400 hover:text-blue-400"
        title="View {pageName} on wiki"
    >
        <span>Wiki</span>
        <ExternalLink class="h-3 w-3" />
    </a>
{/if}
