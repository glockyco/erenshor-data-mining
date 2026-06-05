return {
	["item:copper_armor_mold"] = {
		name = "Copper Armor Mold",
		page = "Copper Armor Mold",
		image = "Copper Armor Mold.png",
		type = "Mold",
		buyValue = 250,
		sellValue = 62,
		ingredients = {
			{
				quantity = 2,
				link = { kind = "item", page = "Chunk of Copper Ore", text = "Chunk of Copper Ore" },
			},
			{ quantity = 1, link = { kind = "item", page = "Tanned Hide", text = "Tanned Hide" } },
		},
		rewards = {
			{
				quantity = 1,
				link = { kind = "item", page = "Copper Breastplate", text = "Copper Breastplate" },
			},
		},
	},
}
