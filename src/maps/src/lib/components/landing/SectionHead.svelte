<script lang="ts">
    import CoordTag from './CoordTag.svelte';
    let { title }: { title: string } = $props();
</script>

<div class="sec-head">
    <div>
        <CoordTag />
        <h2>{title}</h2>
    </div>
</div>

<style>
    .sec-head {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 20px;
        margin-bottom: 24px;
    }
    h2 {
        position: relative;
        margin: 0;
        padding-bottom: 12px;
        font-family: var(--font-display);
        font-size: clamp(1.55rem, 3vw, 2.2rem);
        font-weight: 800;
        letter-spacing: -0.01em;
        color: var(--color-ink);
    }
    h2::after {
        content: '';
        position: absolute;
        left: 0;
        bottom: 0;
        width: 42px;
        height: 3px;
        border-radius: 2px;
        background: var(--color-accent);
    }
</style>
