import { describe, expect, it } from 'vitest';
import { aggregateDropVariants } from './drop-variants';

describe('aggregateDropVariants', () => {
	it('leaves a single candidate exactly as it was', () => {
		// The common case must render identically to the unambiguous popup, or
		// disambiguation would change what most NPCs show.
		const single = [
			{ itemName: 'Brackwood Mace', dropProbability: 4.44 },
			{ itemName: 'Luminstone', dropProbability: 1.15 }
		];
		expect(aggregateDropVariants([single])).toEqual([
			{ itemName: 'Brackwood Mace', minProbability: 4.44, maxProbability: 4.44, droppedBy: 1 },
			{ itemName: 'Luminstone', minProbability: 1.15, maxProbability: 1.15, droppedBy: 1 }
		]);
	});

	it('reports a range when candidates disagree on a chance', () => {
		// Naming one endpoint would state a number neither variant has.
		const [drop] = aggregateDropVariants([
			[{ itemName: 'Sea Silk', dropProbability: 2 }],
			[{ itemName: 'Sea Silk', dropProbability: 9 }]
		]);
		expect(drop).toEqual({
			itemName: 'Sea Silk',
			minProbability: 2,
			maxProbability: 9,
			droppedBy: 2
		});
	});

	it('keeps an item only some candidates drop, and says how many', () => {
		// Dropping it would hide loot the player might actually get, which is the
		// failure this aggregation exists to avoid.
		const drops = aggregateDropVariants([
			[{ itemName: 'Shared', dropProbability: 5 }],
			[
				{ itemName: 'Shared', dropProbability: 5 },
				{ itemName: 'Exclusive', dropProbability: 50 }
			]
		]);
		expect(drops.map((drop) => [drop.itemName, drop.droppedBy])).toEqual([
			['Exclusive', 1],
			['Shared', 2]
		]);
	});

	it('orders by best chance, then by name', () => {
		const drops = aggregateDropVariants([
			[
				{ itemName: 'Zinc', dropProbability: 5 },
				{ itemName: 'Alum', dropProbability: 5 },
				{ itemName: 'Rare Thing', dropProbability: 1 }
			],
			[{ itemName: 'Zinc', dropProbability: 40 }]
		]);
		// Zinc leads on its best variant rather than its worst.
		expect(drops.map((drop) => drop.itemName)).toEqual(['Zinc', 'Alum', 'Rare Thing']);
	});

	it('yields nothing for candidates without loot', () => {
		expect(aggregateDropVariants([])).toEqual([]);
		expect(aggregateDropVariants([[], []])).toEqual([]);
	});
});
