<script lang="ts">
    import SectionHead from './SectionHead.svelte';
    import Icon from './Icon.svelte';
    import { line } from './icons';

    const official = [
        {
            icon: line.steam,
            href: 'https://store.steampowered.com/app/2382520/Erenshor/',
            title: 'Erenshor on Steam',
            desc: 'Buy the game on Steam.'
        },
        {
            icon: line.globe,
            href: 'https://erenshor.com/',
            title: 'Official Website',
            desc: 'erenshor.com, by Burgee Media.'
        },
        {
            icon: line.discord,
            href: 'https://discord.gg/erenshor',
            title: 'Official Discord',
            desc: 'News, help, and the community.'
        },
        {
            icon: line.wiki,
            href: 'https://erenshor.wiki.gg/',
            title: 'Official Wiki',
            desc: 'erenshor.wiki.gg, the full game reference.'
        }
    ];

    const community = [
        {
            icon: line.vault,
            href: 'https://erenshorvault.app/',
            title: 'Erenshor Vault',
            desc: 'Community tools, guides & the mod registry.'
        },
        {
            icon: line.lunaris,
            href: 'https://github.com/MizukiBelhi/Lunaris',
            title: 'Lunaris Mod Loader',
            desc: 'Install & update mods while the game runs.'
        },
        {
            icon: line.guide,
            href: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3500398991',
            title: 'Steam Guide',
            desc: 'The maps & spreadsheet, on Steam.'
        },
        {
            icon: line.kofi,
            href: 'https://ko-fi.com/wowmuch',
            title: 'Support on Ko-fi',
            desc: 'Optional thanks if the tools helped, never required.'
        }
    ];

    const groups = [
        { title: 'Official Erenshor', links: official },
        { title: 'Community & support', links: community }
    ];
</script>

<section id="community">
    <SectionHead title="The game & the wider community" />
    <div class="link-groups">
        {#each groups as group (group.title)}
            <div>
                <h3 class="group-title">{group.title}</h3>
                <div class="links">
                    {#each group.links as l (l.href)}
                        <a class="link" href={l.href} target="_blank" rel="noopener">
                            <span class="ic"><Icon paths={l.icon} stroke class="block h-[19px] w-[19px]" /></span>
                            <div>
                                <h4>{l.title}</h4>
                                <p>{l.desc}</p>
                            </div>
                        </a>
                    {/each}
                </div>
            </div>
        {/each}
    </div>
</section>

<style>
    #community {
        padding: clamp(30px, 4.2vw, 56px) 0;
    }
    .link-groups {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 44px;
    }
    .group-title {
        font-family: var(--font-mono);
        font-size: 0.72rem;
        letter-spacing: 0.18em;
        text-transform: uppercase;
        color: var(--color-muted);
        margin: 0 0 6px;
        padding-bottom: 12px;
        border-bottom: 1px solid var(--color-line);
    }
    .links {
        display: flex;
        flex-direction: column;
    }
    .link {
        display: flex;
        align-items: center;
        gap: 15px;
        padding: 14px 12px;
        text-decoration: none;
        color: inherit;
        border-bottom: 1px solid var(--color-line);
        border-radius: 10px;
        transition: background 0.15s;
    }
    .link:last-child {
        border-bottom: none;
    }
    .link:hover {
        background: var(--color-surface);
    }
    .ic {
        flex: none;
        width: 40px;
        height: 40px;
        border-radius: 10px;
        display: grid;
        place-items: center;
        background: var(--color-surface);
        border: 1px solid var(--color-line);
        color: var(--color-accent);
        transition: border-color 0.15s;
    }
    .link:hover .ic {
        border-color: var(--color-accent);
    }
    h4 {
        margin: 0 0 0.12em;
        font-size: 1rem;
        color: var(--color-ink);
        font-family: var(--font-display);
        font-weight: 700;
    }
    p {
        margin: 0;
        font-size: 0.85rem;
        color: var(--color-muted);
    }
    @media (max-width: 880px) {
        .link-groups {
            grid-template-columns: 1fr;
            gap: 28px;
        }
    }
</style>
