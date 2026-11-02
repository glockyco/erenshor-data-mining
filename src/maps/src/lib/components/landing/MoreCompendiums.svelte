<!--
  The other game compendiums, after the game's own community links: equal cards
  with the logo above the name, three in a row and full-width rows on phones.
-->
<script lang="ts">
    import { OTHER_COMPENDIUMS, compendiumIconUrl } from '$lib/compendiums';
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -->
<section id="more-compendiums" aria-labelledby="more-compendiums-title">
    <h2 id="more-compendiums-title">More Compendiums</h2>
    <ul>
        {#each OTHER_COMPENDIUMS as compendium (compendium.icon)}
            <li>
                <a href={compendium.url}>
                    <img
                        src={compendiumIconUrl(compendium)}
                        alt=""
                        width="128"
                        height="128"
                        loading="lazy"
                    />
                    {compendium.name}
                </a>
            </li>
        {/each}
    </ul>
</section>

<style>
    section {
        margin-top: clamp(24px, 3vw, 40px);
        padding: clamp(28px, 3.5vw, 44px) 0 clamp(36px, 4.5vw, 60px);
        border-top: 1px solid var(--color-line);
    }
    h2 {
        margin: 0 0 1rem;
        font-family: var(--font-display);
        font-size: 1.45rem;
        font-weight: 800;
        color: var(--color-ink);
    }
    ul {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1rem;
        margin: 0;
        padding: 0;
        list-style: none;
    }
    a {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.75rem;
        padding: 1.4rem 1rem;
        border: 1px solid var(--color-line);
        border-radius: 10px;
        background: var(--color-surface);
        color: var(--color-ink);
        font-weight: 700;
        text-align: center;
        text-decoration: none;
        transition: border-color 0.15s;
    }
    a:hover {
        border-color: color-mix(in srgb, var(--color-accent) 55%, transparent);
    }
    img {
        width: 4rem;
        height: 4rem;
        object-fit: contain;
    }
    @media (max-width: 639px) {
        ul {
            grid-template-columns: minmax(0, 1fr);
        }
        a {
            flex-direction: row;
            gap: 1rem;
            padding: 1rem;
            text-align: start;
        }
        img {
            width: 3rem;
            height: 3rem;
        }
    }
</style>
