<!-- A survey marker beside a section heading. The X/Y placeholder is replaced
     with the element's real page coordinates at runtime (see coordinates.ts).
     The class name `coord-tag` is queried globally, so it must stay literal. -->
<span class="coord-tag"><b>X</b> 0 · <b>Y</b> 0</span>

<style>
    .coord-tag {
        display: inline-block;
        font-family: var(--font-mono);
        font-size: 0.66rem;
        letter-spacing: 0.12em;
        color: var(--color-muted);
        border: 1px solid var(--color-line);
        border-radius: 6px;
        padding: 3px 8px;
        margin-bottom: 10px;
    }
    /* :global because the <b> elements are re-created via innerHTML at runtime. */
    .coord-tag :global(b) {
        color: var(--color-accent);
        font-weight: 500;
    }
</style>
