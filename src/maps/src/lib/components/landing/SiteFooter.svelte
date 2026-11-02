<!--
  The footer of every page but the maps. Each group of links is a band with its
  label beside it, and the other compendiums are equal cards with their logos,
  the structure every compendium's footer shares in its own style. The generous
  bottom padding reserves space for the section lens nav, which floats
  bottom-right at every width.
-->
<script lang="ts">
    import { OTHER_COMPENDIUMS, compendiumIconUrl } from '$lib/compendiums';
    import {
        compareFreshness,
        isNotablyStale,
        type BuildFeed,
        type BuildProvenance,
        type Freshness
    } from '$lib/steam-builds';

    // Null whenever the export did not record a build. An honest older date is
    // fine for a reference tool; a fabricated "updated today" is not, so the
    // line is omitted rather than guessed.
    let { provenance = null }: { provenance?: BuildProvenance | null } = $props();

    const buildDate = $derived.by(() => {
        if (!provenance) return null;
        const date = new Date(provenance.buildPublishedAt);
        if (Number.isNaN(date.getTime())) return null;
        return date.toLocaleDateString('en-US', {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
            timeZone: 'UTC'
        });
    });

    // The site is prerendered, so the live patch check cannot run at render
    // time the way a server-rendered page would do it. It is a progressive
    // enhancement instead: the build and its date are already in the static
    // HTML, and this only adds how that build compares to the live game. On any
    // failure the comparison stays absent rather than claiming currency.
    let freshness = $state<Freshness | null>(null);

    $effect(() => {
        const stamp = provenance;
        if (!stamp) return;

        const aborter = new AbortController();
        fetch('/api/game-version', { signal: aborter.signal })
            .then((response) => (response.ok ? (response.json() as Promise<BuildFeed>) : null))
            .then((feed) => {
                freshness = compareFreshness(stamp, feed?.builds);
            })
            .catch(() => {
                freshness = null;
            });

        return () => aborter.abort();
    });

    // How old the data is answers "can I trust this" without the reader needing
    // to know Erenshor's release cadence, but it is only true at read time, so a
    // prerendered copy would be wrong the day after a deploy. It rides along
    // with the live comparison rather than being baked into the HTML.
    const ageLabel = $derived.by(() => {
        if (!freshness) return null;
        if (freshness.daysOld === 0) return 'today';
        if (freshness.daysOld === 1) return 'yesterday';
        return `${freshness.daysOld} days ago`;
    });

    // The count is exact: the exported build is located in the feed by ID, and
    // only builds the developer announced are counted, so unannounced rebuilds
    // never inflate it into something a player would not recognise as a patch.
    // Days alone could not distinguish a quiet week from one that shipped daily.
    const freshnessLabel = $derived.by(() => {
        if (!freshness) return null;
        if (freshness.state === 'current') return 'up to date';
        const count = `${freshness.patchesBehind}${freshness.saturated ? '+' : ''}`;
        const plural = freshness.patchesBehind === 1 && !freshness.saturated ? '' : 'es';
        return `${count} patch${plural} behind`;
    });
    const notablyStale = $derived(freshness ? isNotablyStale(freshness) : false);

    const siteLinks = [
        { label: 'World Map', href: '/map' },
        { label: 'Zone Maps', href: '/zone-maps' },
        { label: 'Adventure Guide', href: '/adventure-guide' },
        { label: 'Mods', href: '/mod' },
        { label: 'Spreadsheet', href: '/spreadsheet' },
        { label: 'About', href: '/#about' }
    ];
    const projectLinks = [
        { label: 'Code on GitHub', href: 'https://github.com/glockyco/erenshor-data-mining' },
        { label: 'Support on Ko-fi', href: 'https://ko-fi.com/wowmuch' }
    ];
    // Every compendium's footer starts this band with its game on Steam and the
    // game's official Discord.
    const communityLinks = [
        {
            label: 'Erenshor on Steam',
            href: 'https://store.steampowered.com/app/2382520/Erenshor/'
        },
        { label: 'Erenshor Discord', href: 'https://discord.gg/erenshor' },
        { label: 'Official Website', href: 'https://erenshor.com/' },
        { label: 'Official Wiki', href: 'https://erenshor.wiki.gg/' },
        { label: 'Erenshor Vault', href: 'https://erenshorvault.app/' },
        { label: 'Lunaris Mod Loader', href: 'https://github.com/MizukiBelhi/Lunaris' },
        {
            label: 'Steam Guide',
            href: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3500398991'
        }
    ];
    const bands = [
        { id: 'footer-site', title: 'This Site', links: siteLinks },
        { id: 'footer-project', title: 'Project', links: projectLinks },
        { id: 'footer-community', title: 'Game & Community', links: communityLinks }
    ];
</script>

<!-- eslint-disable svelte/no-navigation-without-resolve -->
<footer class="site-footer mt-2 border-t border-line">
    <div
        class="mx-auto max-w-[1140px] px-4 pt-[30px] pb-20 text-[0.88rem] text-muted min-[480px]:px-7"
    >
        <h2>Erenshor Maps</h2>
        {#each bands as band (band.id)}
            <section aria-labelledby={band.id}>
                <h3 id={band.id}>{band.title}</h3>
                <ul>
                    {#each band.links as link (link.href)}
                        <li><a href={link.href}>{link.label}</a></li>
                    {/each}
                </ul>
            </section>
        {/each}
        <section class="others-band" aria-labelledby="footer-others">
            <h3 id="footer-others">Other Compendiums</h3>
            <ul class="others">
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
                            <span>{compendium.name}</span>
                        </a>
                    </li>
                {/each}
            </ul>
        </section>
        <div class="notes">
            {#if provenance && buildDate}
                <p>
                    Game data from <time
                        datetime={provenance.buildPublishedAt}
                        title="Steam build {provenance.gameBuildId}">{buildDate}</time
                    >{#if ageLabel}&nbsp;<span class="whitespace-nowrap">({ageLabel})</span
                        >{/if}{#if freshnessLabel}&nbsp;<span
                            class={notablyStale ? 'text-accent' : 'text-muted'}
                            >&middot; {#if freshness?.latest}<a
                                    class="freshness"
                                    href={freshness.latest.url}
                                    rel="noreferrer"
                                    title={freshness.latest.notesTitle}>{freshnessLabel}</a
                                >{:else}{freshnessLabel}{/if}</span
                        >{/if}
                </p>
            {/if}
            <p>Erenshor Maps. A fan project, not affiliated with Burgee Media.</p>
        </div>
    </div>
</footer>

<style>
    h2 {
        margin: 0 0 0.5rem;
        font-family: var(--font-display);
        font-size: 1.15rem;
        font-weight: 800;
        color: var(--color-ink);
    }
    section {
        display: grid;
        grid-template-columns: 11rem minmax(0, 1fr);
        align-items: baseline;
        gap: 0.5rem 1.25rem;
        padding: 0.85rem 0;
        border-bottom: 1px solid var(--color-line);
    }
    /* The label sits at the middle of the cards rather than on the baseline of their names. */
    .others-band {
        align-items: center;
    }
    h3 {
        margin: 0;
        font-family: var(--font-mono);
        font-size: 0.68rem;
        font-weight: 400;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--color-muted);
    }
    ul {
        display: flex;
        flex-wrap: wrap;
        gap: 0.125rem 1.375rem;
        margin: 0;
        padding: 0;
        list-style: none;
    }
    ul a {
        display: inline-flex;
        align-items: center;
        min-height: 1.75rem;
        color: var(--color-accent);
        text-decoration: none;
    }
    ul a:hover {
        text-decoration: underline;
    }
    .others {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.75rem;
    }
    .others a {
        gap: 0.6rem;
        width: 100%;
        min-height: 2.75rem;
        padding: 0 0.75rem;
        border: 1px solid var(--color-line);
        border-radius: 8px;
        background: var(--color-surface);
        color: var(--color-ink);
        font-weight: 600;
        white-space: nowrap;
    }
    .others a:hover {
        border-color: color-mix(in srgb, var(--color-accent) 55%, transparent);
        text-decoration: none;
    }
    .others img {
        flex: none;
        width: 1.75rem;
        height: 1.75rem;
        object-fit: contain;
    }
    .notes {
        display: grid;
        gap: 0.35rem;
        padding-top: 1rem;
    }
    .notes p {
        margin: 0;
        text-wrap: pretty;
    }
    .freshness {
        color: inherit;
        text-decoration: underline dotted;
        text-underline-offset: 2px;
    }
    .freshness:hover {
        text-decoration-style: solid;
    }
    @media (max-width: 879px) {
        section {
            grid-template-columns: minmax(0, 1fr);
        }
    }
    @media (max-width: 639px) {
        .others {
            grid-template-columns: minmax(0, 1fr);
        }
    }
</style>
