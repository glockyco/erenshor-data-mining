export type BaseMarker = {
	coordinateId: number;
	position: { x: number, y: number };
	popup?: string;
};

export type AchievementTriggerMarker = BaseMarker & {
	category: 'achievement-trigger';
};

export type CharacterMarker = BaseMarker & {
	category: 'character';
	isEnabled: boolean;
	isUnique: boolean;
};

export type DoorMarker = BaseMarker & {
	category: 'door';
};

export type ForgeMarker = BaseMarker & {
	category: 'forge';
};

export type ItemBagMarker = BaseMarker & {
	category: 'item-bag';
};

export type MiningNodeMarker = BaseMarker & {
	category: 'mining-node';
};

export type SecretPassageMarker = BaseMarker & {
	category: 'secret-passage';
}

export type SpawnPointMarker = BaseMarker & {
	category: 'spawn-point';
	isEnabled: boolean;
	hasUnique: boolean;
	hasRare: boolean;
};

export type TeleportMarker = BaseMarker & {
	category: 'teleport';
};

export type TreasureLocMarker = BaseMarker & {
	category: 'treasure-loc';
};

export type WaterMarker = BaseMarker & {
	category: 'water';
};

export type WishingWellMarker = BaseMarker & {
	category: 'wishing-well';
};

export type ZoneLineMarker = BaseMarker & {
	category: 'zone-line';
	isEnabled: boolean;
};

export type Marker =
	| AchievementTriggerMarker
	| CharacterMarker
	| DoorMarker
	| ForgeMarker
	| ItemBagMarker
	| MiningNodeMarker
	| SecretPassageMarker
	| SpawnPointMarker
	| TeleportMarker
	| TreasureLocMarker
	| WaterMarker
	| WishingWellMarker
	| ZoneLineMarker;
