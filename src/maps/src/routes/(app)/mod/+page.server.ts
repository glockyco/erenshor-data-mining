import type { PageServerLoad } from './$types';
import { readFileSync } from 'fs';
import { resolve } from 'path';

interface ModMetadata {
    id: string;
    name: string;
    displayName: string;
    description: string;
    status: 'current' | 'legacy';
    port: number;
    version: string;
    downloadUrl: string;
    gifUrl: string;
    releaseDate: string;
    features: string[];
}

interface ModsData {
    mods: ModMetadata[];
}

export const load: PageServerLoad = async () => {
    try {
        const metadataPath = resolve('static', 'mods-metadata.json');
        const metadataJson = readFileSync(metadataPath, 'utf-8');
        const modsMetadata: ModsData = JSON.parse(metadataJson);

        return {
            modsMetadata
        };
    } catch (error) {
        console.error('Failed to load mods metadata:', error);
        return {
            modsMetadata: { mods: [] }
        };
    }
};
