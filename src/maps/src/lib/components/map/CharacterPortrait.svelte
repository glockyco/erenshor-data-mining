<script lang="ts">
    interface Props {
        hash: string | null;
    }

    let { hash }: Props = $props();
</script>

{#if hash}
    <img
        src={`/characters/${hash}.w96.webp`}
        srcset={`/characters/${hash}.w96.webp 1x, /characters/${hash}.w192.webp 2x`}
        alt=""
        width="96"
        height="96"
        class="mx-auto block h-24 w-24 shrink-0 object-contain"
    />
{/if}
