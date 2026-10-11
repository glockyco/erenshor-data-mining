-- Module:Erenshor/Data/VendorStock
-- Fixture for the local stack, in the format that `erenshor wiki generate-lua` writes.
return {
	["character:captain_rowan"] = {
		{
			["item"] = "item:healing_draught",
			["price"] = 25,
			["type"] = "Consumable",
			["typePage"] = "Consumables",
		},
		{
			["item"] = "item:copper_armor_mold",
			["price"] = 50,
			["type"] = "Mold",
			["typePage"] = "Crafting",
		},
		{
			["item"] = "item:magical_bag",
			["price"] = 10,
			["type"] = "General",
		},
		{
			["item"] = "item:ember_longsword",
			["price"] = 120,
			["quests"] = {
				"quest:magical_sword",
			},
			["type"] = "Weapon",
			["typePage"] = "Weapons",
		},
		{
			["furniture"] = {
				"item:lucky_charm",
			},
			["item"] = "item:bear_pelt",
			["price"] = 300,
			["type"] = "Crafting",
			["typePage"] = "Crafting",
		},
	},
}
