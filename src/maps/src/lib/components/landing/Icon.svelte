<script lang="ts">
    // Renders a trusted local SVG path string from `icons.ts`. The markup is a
    // compile-time constant (never user input), so `{@html}` is safe here.
    interface Props {
        paths: string;
        class?: string;
        stroke?: boolean;
    }
    let { paths, class: cls = '', stroke = false }: Props = $props();
</script>

<!-- eslint-disable svelte/no-at-html-tags -- this component only renders trusted local icon constants -->
{#if stroke}
    <svg
        viewBox="0 0 24 24"
        class={cls}
        fill="none"
        stroke="currentColor"
        stroke-width="1.8"
        stroke-linecap="round"
        stroke-linejoin="round">{@html paths}</svg
    >
{:else}
    <svg viewBox="0 0 24 24" class={cls} fill="currentColor">{@html paths}</svg>
{/if}
