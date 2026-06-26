<script lang="ts">
    import SectionHead from './SectionHead.svelte';
    import { FAQ_ITEMS } from '$lib/seo/faq';
</script>

<section id="faq">
    <SectionHead title="Common questions" />
    <div class="faq">
        {#each FAQ_ITEMS as item (item.question)}
            <div class="qa">
                <h3>{item.question}</h3>
                <p>
                    {#each item.answer as seg, i (i)}
                        {#if typeof seg === 'string'}
                            {seg}
                        {:else if seg.external}
                            <a href={seg.href} target="_blank" rel="noopener noreferrer"
                                >{seg.text}</a
                            >
                        {:else}
                            <a href={seg.href}>{seg.text}</a>
                        {/if}
                    {/each}
                </p>
            </div>
        {/each}
    </div>
</section>

<style>
    #faq {
        padding: clamp(30px, 4.2vw, 56px) 0;
    }
    .faq {
        display: grid;
        gap: 26px;
    }
    .qa h3 {
        font-family: var(--font-display);
        font-size: 1.12rem;
        font-weight: 700;
        margin: 0 0 0.4em;
        color: var(--color-ink);
    }
    .qa p {
        max-width: 64ch;
        margin: 0;
        line-height: 1.6;
        color: color-mix(in oklab, var(--color-ink) 84%, var(--color-bg));
    }
    .qa a {
        color: var(--color-accent);
        text-decoration: none;
        border-bottom: 1px solid color-mix(in srgb, var(--color-accent) 45%, transparent);
    }
</style>
