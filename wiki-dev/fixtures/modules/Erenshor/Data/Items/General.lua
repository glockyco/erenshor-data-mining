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
			{
				type = "starting",
				sourceKey = "class:Arcanist",
			},
		},
		usedIn = {
			{
				type = "craft_material",
				targetKey = "item:template - copper armor mold",
				quantity = 2,
				slot = 1,
			},
			{
				type = "quest_requirement",
				targetKey = "quest:an ore for the forge",
				quantity = 1,
			},
		},
	},
	["item:ore - planar stone"] = {
		name = "Planar Stone",
		page = "Planar Stone",
		image = "Planar Stone.png",
		type = "General",
		usedIn = {
			{ type = "upgrade_material", targetKey = "item:template - an otherwordly mold" },
		},
	},
	["item:template - inert diamond"] = {
		name = "Inert Diamond",
		page = "Inert Diamond",
		image = "Inert Diamond.png",
		type = "General",
		usedIn = {
			{ type = "blessing_removal_material", targetKey = "item:template - inert diamond" },
		},
	},
	["item:ore - bronze ore"] = {
		name = "Bronze Ore",
		page = "Bronze Ore",
		image = "Bronze Ore.png",
		type = "General",
		usedIn = {
			{
				type = "craft_material",
				targetKey = "item:template - copper armor mold",
				quantity = 2,
				slot = 1,
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
