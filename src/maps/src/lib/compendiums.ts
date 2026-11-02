/** A game compendium, with the logo that compendiums.org shows for it. */
interface Compendium {
    name: string;
    url: string;
    icon: string;
}

/** The game compendiums, in the order compendiums.org lists them. */
export const COMPENDIUMS: readonly Compendium[] = [
    { name: 'Afallon', url: 'https://afallon.compendiums.org/', icon: 'afallon' },
    {
        name: 'Ancient Kingdoms',
        url: 'https://ancient-kingdoms.compendiums.org/',
        icon: 'ancient-kingdoms'
    },
    { name: 'Erenshor', url: 'https://erenshor.compendiums.org/', icon: 'erenshor' },
    { name: 'The Bloodline', url: 'https://the-bloodline.compendiums.org/', icon: 'the-bloodline' }
];

/** This compendium's entry in the list. */
export const THIS_COMPENDIUM = 'erenshor';

/** The compendiums for the other games. */
export const OTHER_COMPENDIUMS = COMPENDIUMS.filter(({ icon }) => icon !== THIS_COMPENDIUM);

export const compendiumIconUrl = (compendium: Compendium): string =>
    `https://compendiums.org/icons/${compendium.icon}.webp`;
