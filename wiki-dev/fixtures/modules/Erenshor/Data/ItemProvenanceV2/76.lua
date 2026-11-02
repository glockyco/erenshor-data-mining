return {
	byKey = {
		["item:ember_longsword"] = {
			references = {
				["character:captain_rowan"] = {
					key = "character:captain_rowan",
					name = "Captain Rowan",
					page = "Captain Rowan",
				},
				["item:magical_bag"] = {
					key = "item:magical_bag",
					name = "Magical Bag",
					page = "Magical Bag",
				},
				["item:ember_longsword"] = {
					key = "item:ember_longsword",
					name = "Ember Longsword",
					page = "Ember Longsword",
				},
			},
			sources = {
				{
					source_key = "acq:fixture-vendor",
					item_stable_key = "item:ember_longsword",
					kind = "vendor",
					source_stable_key = "character:captain_rowan",
					probability_kind = "not_applicable",
					quantity_kind = "exact",
					quantity_min = 1,
					quantity_max = 1,
				},
				{
					source_key = "acq:fixture-yield",
					item_stable_key = "item:ember_longsword",
					kind = "item_drop",
					source_stable_key = "item:magical_bag",
					mechanic = "fixture_wells",
					probability_kind = "exact",
					probability_min = 12.5,
					probability_max = 12.5,
					probability_basis = "per_use",
					quantity_kind = "exact",
					quantity_min = 1,
					quantity_max = 1,
				},
			},
			usages = {},
			status = { item_stable_key = "item:ember_longsword", disposition = "current" },
		},
	},
	mechanism_parameters = {
		fixture_wells = {
			{
				mechanic_key = "fixture_wells",
				parameter_index = 0,
				gate_key = "chance",
				predicate = "formula_operand",
				value = "chance_per_stone_pair",
				minimum = 40,
				phase = "mechanic_parameter",
			},
		},
	},
}
