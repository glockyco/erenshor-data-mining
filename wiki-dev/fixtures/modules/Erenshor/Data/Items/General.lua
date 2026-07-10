return {
	["item:magical_bag"] = {
		name = "Magical Bag",
		page = "Magical Bag",
		image = "Magical Bag.png",
		type = "General",
		description = "A surprisingly roomy bag woven from enchanted thread.",
		buyValue = 950000,
		sellValue = 237500,
		containerDrops = {
			{ item = "item:bear_pelt", probability = 50.0, guaranteed = true },
			{ item = "item:bear_claw", probability = 30.0, guaranteed = true },
			{ item = "item:bear_meat", probability = 20.0 },
		},
		obtainedFrom = {
			{
				type = "drop",
				sourceKey = "character:a_grizzly_bear",
				probability = 12.5,
				guaranteed = true,
			},
			{
				type = "fishing",
				sourceKey = "water:brake:287.10:7.50:247.80",
				probability = 5.9375,
				condition = "day",
			},
			{
				type = "item_use",
				sourceKey = "item:gen - bag of offering stones",
			},
		},
	},
	["item:bear_pelt"] = {
		name = "Bear Pelt",
		page = "Bear Pelt",
		image = "Bear Pelt.png",
		type = "General",
		unique = true,
		sellValue = 120,
	},
	["item:bear_claw"] = {
		name = "Bear Claw",
		page = "Bear Claw",
		image = "Bear Claw.png",
		type = "General",
		sellValue = 80,
	},
	["item:bear_meat"] = {
		name = "Bear Meat",
		page = "Bear Meat",
		image = "Bear Meat.png",
		type = "General",
		sellValue = 15,
	},
}
