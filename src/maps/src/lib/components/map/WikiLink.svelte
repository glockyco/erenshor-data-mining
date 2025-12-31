<script lang="ts">
    import ExternalLink from '@lucide/svelte/icons/external-link';

    interface Props {
        name: string;
    }

    let { name }: Props = $props();

    const url = $derived(`https://erenshor.wiki.gg/wiki/${encodeURIComponent(name)}`);
</script>

<a
    href={url}
    class="flex items-center gap-1 text-xs text-zinc-400 hover:text-blue-400"
    title="View {name} on wiki"
>
    <span>Wiki</span>
    <ExternalLink class="h-3 w-3" />
</a>
