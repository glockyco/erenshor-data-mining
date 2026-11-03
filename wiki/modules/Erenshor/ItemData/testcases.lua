local ItemData = require("Module:Erenshor/ItemData")
local Provenance = require("Module:Erenshor/ItemData/Provenance")
local Details = require("Module:Erenshor/ItemData/Details")
local REFERENCES = mw.loadData("Module:Erenshor/Data/Links").byKey

local p = {}
local function contains(text, expected)
	text = mw.text.unstrip(text)
	if not text:find(expected, 1, true) then
		error("Expected ItemData output: " .. expected, 2)
	end
end
local function absent(text, unexpected)
	text = mw.text.unstrip(text)
	if text:find(unexpected, 1, true) then
		error("Unexpected ItemData output: " .. unexpected, 2)
	end
end
local function count(text, needle)
	local n, start = 0, 1
	while true do
		local position = text:find(needle, start, true)
		if not position then
			return n
		end
		n, start = n + 1, position + #needle
	end
end

function p.shards()
	for _, split in ipairs({
		{ key = "item:split-left", shard = "1a0", fact = "acquisition:split-left" },
		{ key = "item:split-right", shard = "1af", fact = "acquisition:split-right" },
	}) do
		local relation =
			ItemData.provenance({ stableKey = split.key, provenanceShard = split.shard })
		local seen = 0
		for _, acquisition in ipairs(relation.sources) do
			if acquisition.source_key ~= split.fact then
				error("ItemData provenance split selected another owner's fact")
			end
			seen = seen + 1
		end
		if seen ~= 1 then
			error("ItemData provenance split lost or duplicated an owner")
		end
	end
	return "PASS Erenshor ItemData adaptive shard reader"
end

function p.nativeReferences()
	local copy = "character:a highwayman raider (1):elderstone:-732.18:-51.70:194.52"
	local quest, target = "quest:amethikeys", "quest:clearingthebonepits"
	local references = {
		[copy] = { key = copy, name = "A Highwayman Raider" },
		[quest] = { key = quest, name = "A Retired Locksmith" },
		[target] = { key = target, name = "Clearing the Bonepits" },
		["zone:PortAzure"] = REFERENCES["zone:PortAzure"],
	}
	local data = {
		references = references,
		sources = {
			{
				source_key = "acquisition:native-reference",
				kind = "character_drop",
				source_stable_key = copy,
				source_copy_stable_key = copy,
				conditions = {
					{
						gate_key = "native-quest",
						alternative_index = 0,
						gate_index = 0,
						atom_index = 0,
						phase = "availability",
						predicate = "quest_done",
						reference_stable_key = quest,
					},
				},
				place_set_key = "native-reference",
			},
		},
		usages = {
			{
				use_key = "use:native-reference",
				kind = "quest_requirement",
				target_stable_key = target,
			},
		},
	}
	data.places = {
		["native-reference"] = {
			{
				place_key = "location:native-reference",
				relation = "fixed",
				source_copy_stable_key = copy,
				zone_stable_key = "zone:PortAzure",
				conditions = {
					{
						gate_index = 0,
						gate_key = "local-quest",
						alternative_index = 0,
						atom_index = 0,
						phase = "availability",
						predicate = "quest_not_done",
						reference_stable_key = target,
					},
				},
			},
		},
	}
	local first = Provenance.render(data)
	contains(first, "A Highwayman Raider")
	contains(first, "A Retired Locksmith")
	contains(first, "Clearing the Bonepits")
	contains(first, 'data-erenshor-source-copy-stable-key="' .. copy .. '"')
	contains(first, 'data-erenshor-reference="' .. quest .. '"')
	contains(first, 'data-erenshor-target-key="' .. target .. '"')
	contains(first, 'data-erenshor-key="zone:PortAzure"')
	absent(first, "Unresolved Erenshor")
	absent(first, "[[A Highwayman Raider")
	absent(first, "[[A Retired Locksmith")
	absent(first, "[[Clearing the Bonepits")
	local linked = ItemData.renderArgs(mw.getCurrentFrame(), { stablekey = "item:ember_longsword" })
	contains(linked, 'data-erenshor-key="character:captain_rowan"')
	absent(linked, "A Highwayman Raider")
	if mw.text.unstrip(Provenance.render(data)) ~= mw.text.unstrip(first) then
		error("Another item root changed native reference rendering")
	end
	if pcall(Provenance.identity, copy, {}) then
		error("Unknown native reference reused another root's catalog")
	end
	if pcall(Provenance.identity, quest, { [quest] = { key = target, name = "Wrong quest" } }) then
		error("Native reference accepted another identity")
	end
	local escaped =
		Provenance.identity(quest, { [quest] = { key = quest, name = "Native <quest> & name" } })
	contains(escaped, "Native &lt;quest&gt; &amp; name")
	return "PASS Erenshor ItemData native references"
end

function p.run()
	p.nativeReferences()
	p.shards()
	local frame = mw.getCurrentFrame()
	local weapon = ItemData.renderArgs(frame, {
		stablekey = "item:ember_longsword",
		damage = "999999",
		type = "Editor classification",
		othersource = "An editor's exact note.",
	})
	contains(weapon, 'data-erenshor-key="item:ember_longsword"')
	contains(weapon, "Item data calls with unsupported parameters")
	contains(weapon, "Editor classification")
	contains(weapon, "An editor's exact note.")
	contains(weapon, "Old Ember Blade")
	contains(weapon, "101")
	absent(weapon, 'data-source="build"')
	absent(weapon, "build fixture")
	local internalBuild = ItemData.resolve("item:ember_longsword").build
	if internalBuild == nil or internalBuild.gameBuildId ~= "fixture" then
		error("Internal item provenance lost build metadata")
	end
	absent(weapon, "999999")
	if count(weapon, 'class="item-tooltip-quality"') ~= 8 then
		error("ItemData lost a quality card")
	end
	for _, quality in ipairs({
		"Standard",
		"Improved +1",
		"Improved +2",
		"Improved +3",
		"Improved +4",
		"Improved +5",
		"Blessed",
		"Ascended",
	}) do
		contains(weapon, 'data-erenshor-quality="' .. quality .. '"')
	end
	if count(weapon, 'class="item-spell-details"') ~= 16 then
		error("Every quality must retain both inline effects")
	end
	contains(weapon, "Must Equip to Cast")
	contains(
		ItemData.renderArgs(frame, { stablekey = "item:ember_longsword", damage = "" }),
		"Item data calls with unsupported parameters"
	)
	local unchanged = "  Editor text with whitespace.  "
	contains(
		ItemData.renderArgs(frame, { stablekey = "item:magical_bag", othersource = unchanged }),
		unchanged
	)
	local inactive = {}
	for key, value in pairs(ItemData.resolve("item:ember_longsword")) do
		inactive[key] = value
	end
	inactive.effects = { { kind = "weaponProc", spellKey = "spell:ember_proc", chance = 0 } }
	absent(Details.render(frame, inactive), 'class="item-spell-details"')
	inactive.slot = "Head"
	inactive.effects = { { kind = "weaponProc", spellKey = "spell:ember_proc", chance = 20 } }
	absent(Details.render(frame, inactive), 'class="item-spell-details"')
	contains(
		Details.render(frame, {
			stableKey = "item:cosmetic-fixture",
			name = "Cosmetic fixture",
			kind = "cosmetic",
			type = "Cosmetic",
		}),
		"item-tooltip-general"
	)
	contains(
		Details.render(frame, {
			stableKey = "item:furniture-fixture",
			name = "Furniture fixture",
			kind = "general",
			type = "Furniture",
		}),
		"item-tooltip-general"
	)
	contains(
		Details.description("<color=green>Green text</color>"),
		'<span style="color: #15e300;">Green text</span>'
	)

	local cases = {
		{ "item:abyssal_plate", "item-tooltip-armor" },
		{ "item:lucky_charm", "item-tooltip-charm" },
		{ "item:ember_aura", "item-tooltip-aura" },
		{ "item:scroll_of_ember", "item-tooltip-book" },
		{ "item:sword_mastery_manual", "item-tooltip-book" },
		{ "item:healing_draught", "item-tooltip-consumable" },
		{ "item:copper_armor_mold", "item-tooltip-crafting" },
		{ "item:magical_bag", "item-tooltip-general" },
	}
	for _, case in ipairs(cases) do
		contains(ItemData.renderArgs(frame, { stablekey = case[1] }), case[2])
	end
	local armor = ItemData.renderArgs(frame, { stablekey = "item:abyssal_plate" })
	contains(armor, "Historical Content")
	contains(armor, "Item_Picture_Fixture_render_%28male%29.png")
	contains(armor, "Item_Picture_Fixture_render_%28female%29.png")
	local scroll = ItemData.renderArgs(frame, { stablekey = "item:scroll_of_ember" })
	contains(scroll, "Windblade: 8")
	contains(scroll, 'data-erenshor-key="spell:ember"')
	local book = ItemData.renderArgs(frame, { stablekey = "item:sword_mastery_manual" })
	contains(book, "DO NOT automatically learn")
	local mold = ItemData.renderArgs(frame, { stablekey = "item:copper_armor_mold" })
	contains(mold, "3x ")

	for _, key in ipairs({ "", "Ember Longsword", "spell:ember", "item:not-a-fixture" }) do
		contains(
			ItemData.renderArgs(frame, { stablekey = key }),
			"Item data calls with invalid identities"
		)
	end
	local note = {
		item = "item:ember_longsword",
		kind = "vendor",
		source = "character:captain_rowan",
		text = "Keep this note.",
	}
	local covered = ItemData.sourceNoteArgs(note)
	contains(covered, "Keep this note.")
	contains(covered, "Item data notes covered by game data")
	note.kind = "character_drop"
	absent(ItemData.sourceNoteArgs(note), "Item data notes covered by game data")
	absent(
		ItemData.renderArgs(
			frame,
			{ stablekey = "item:ember_longsword", othersource = "Captain Rowan sells it." }
		),
		"Item data notes covered by game data"
	)

	local data = ItemData.provenance(ItemData.resolve("item:magical_bag"))
	local rendered = Provenance.render(data, ItemData.outcome)
	for _, key in ipairs({ "acq:bag-day", "acq:bag-night", "acq:bag-room", "acq:bag-auction" }) do
		contains(rendered, 'data-erenshor-source-key="' .. key .. '"')
	end
	contains(rendered, 'data-erenshor-use-key="use:bag-recipe"')
	contains(rendered, 'data-erenshor-use-key="use:bag-yield"')
	contains(rendered, 'data-erenshor-outcome-key="acq:fixture-yield"')
	contains(rendered, "12.5%")
	contains(rendered, "Chance per stone pair 40%")
	contains(rendered, "1.25e-06%")
	contains(rendered, "1.25 to 7.5%")
	contains(rendered, 'data-erenshor-predicate="room_furnished"')
	-- An exclusive maximum keeps its meaning next to an inclusive minimum.
	contains(rendered, "below 20")
	absent(rendered, "–below")
	contains(rendered, "Location varies")
	contains(rendered, "May be listed by simulated players")
	absent(rendered, 'hidden="hidden"')
	absent(rendered, "data-erenshor-disposition")
	for _, row in ipairs(data.sources) do
		contains(rendered, 'data-erenshor-source-key="' .. row.source_key .. '"')
	end
	for _, row in ipairs(data.usages) do
		contains(rendered, 'data-erenshor-use-key="' .. row.use_key .. '"')
	end
	local global = Provenance.render({
		sources = {
			{
				source_key = "water:global",
				kind = "fishing",
				mechanic = "fishing_global_replacement",
				probability_kind = "exact",
				probability_basis = "per_successful_catch",
				probability_min = 1.25,
				probability_max = 1.25,
			},
			{
				source_key = "water:enhanced",
				kind = "fishing",
				probability_kind = "exact",
				probability_min = 7.1875,
				probability_max = 7.1875,
			},
		},
		usages = {},
	})
	if count(global, "Any water") ~= 1 then
		error("Global fishing must render one summary")
	end
	contains(global, "Chance: 1.25%")
	contains(global, "7.1875%")
	contains(global, 'data-erenshor-source-key="water:global"')
	contains(global, 'data-erenshor-source-key="water:enhanced"')
	if count(global, '<th scope="row">Fished in</th>') ~= 2 then
		error("Every public fishing source must render its own row")
	end
	absent(global, 'hidden="hidden"')
	local phased = Provenance.conditions({
		{
			gate_key = "input",
			alternative_index = 0,
			gate_index = 0,
			atom_index = 0,
			phase = "operation_input",
			predicate = "item_held",
			reference_stable_key = "item:copper_armor_mold",
			minimum = 1,
		},
		{
			gate_key = "output",
			alternative_index = 0,
			gate_index = 1,
			atom_index = 0,
			phase = "operation_outcome",
			predicate = "quality",
			value = "blessed",
		},
	}, REFERENCES)
	contains(phased, 'data-erenshor-phase="operation_input"')
	contains(phased, 'data-erenshor-phase="operation_outcome"')
	contains(phased, "Result:")
	local bounded = Provenance.render({
		sources = {
			{
				source_key = "bounded",
				kind = "vendor",
				probability_kind = "not_applicable",
				quantity_kind = "bounded",
				quantity_min = 1,
			},
		},
		usages = {},
	})
	contains(bounded, "Quantity: at least 1")
	local unknown = Provenance.render({
		sources = {
			{
				source_key = "unknown",
				kind = "vendor",
				probability_kind = "unknown",
				quantity_kind = "unknown",
			},
		},
		usages = {},
	})
	absent(unknown, "Quantity:")
	local class = Provenance.conditions({
		{
			gate_key = "class",
			alternative_index = 0,
			gate_index = 0,
			atom_index = 0,
			phase = "availability",
			predicate = "actor_class",
			actor = "player",
			reference_stable_key = "class:paladin",
		},
	}, REFERENCES)
	contains(class, "Paladin")
	contains(
		Provenance.acquisitionDetails({
			quantity_kind = "exact",
			quantity_min = 2,
			quantity_max = 2,
			probability_kind = "exact",
			probability_min = 12.5,
			probability_max = 12.5,
		}),
		"12.5%"
	)
	contains(
		Provenance.locations({
			{ place_key = "formatter-fixture", relation = "unlocated", conditions = {} },
		}),
		"Location varies"
	)
	contains(Provenance.acquisitionDetails({ guaranteed = true }), "Guaranteed item")
	absent(Provenance.acquisitionDetails({ guaranteed = false }), "Guaranteed item")
	local exactKey =
		ItemData.renderArgs(frame, { stablekey = "item:arm - 19  - ancient guardian sleeve" })
	contains(exactKey, 'data-erenshor-key="item:arm - 19&#32;&#32;- ancient guardian sleeve"')
	contains(exactKey, 'data-erenshor-provenance="acq:key&#32;&#32;fixture"')
	contains(exactKey, "room L1")
	contains(exactKey, "Stone Training Set")
	contains(
		ItemData.renderArgs(frame, { stablekey = "item:arm - 19 - ancient guardian sleeve" }),
		"Item data calls with invalid identities"
	)
	local gates = Provenance.conditions({
		{
			gate_key = "time",
			alternative_index = 0,
			gate_index = 0,
			atom_index = 0,
			phase = "availability",
			predicate = "time_of_day",
			value = "day",
		},
		{
			gate_key = "time",
			alternative_index = 1,
			gate_index = 0,
			atom_index = 0,
			phase = "availability",
			predicate = "time_of_day",
			value = "night",
		},
		{
			gate_key = "time",
			gate_index = 1,
			alternative_index = 0,
			atom_index = 0,
			phase = "availability",
			predicate = "actor_level",
			actor = "player",
			minimum = 10,
		},
	})
	contains(gates, ")) and (")
	local account = Provenance.conditions({
		{
			gate_key = "claim",
			alternative_index = 0,
			gate_index = 0,
			atom_index = 0,
			predicate = "account_state",
			actor = "account",
			reference_stable_key = "account_state:reliquary_claimed",
			value = "false",
			phase = "availability",
		},
	})
	contains(account, 'data-erenshor-reference="account_state:reliquary_claimed"')
	absent(account, "quest:")
	local questAlias = pcall(Provenance.conditions, {
		{
			gate_key = "claim",
			alternative_index = 0,
			gate_index = 0,
			atom_index = 0,
			predicate = "account_state",
			actor = "account",
			reference_stable_key = "quest:reliquary_claimed",
			value = "false",
			phase = "availability",
		},
	})
	if questAlias then
		error("Account claim state must not accept a quest alias")
	end
	local forge = Provenance.parameters({
		{
			gate_key = "fuel",
			parameter_index = 0,
			predicate = "formula_operand",
			value = "fuel_level",
			minimum = 0,
			maximum = 0,
			phase = "mechanic_parameter",
		},
		{
			gate_key = "counts",
			parameter_index = 1,
			predicate = "formula_operand",
			value = "equal_positive_stone_counts",
			minimum = 1,
			phase = "operation_input",
		},
	})
	contains(forge, "Fuel level 0")
	absent(forge, "Fuel level 0%")
	contains(forge, "Equal-sized stacks of both stones at least 1 each")
	absent(forge, "each%")
	local quality = Provenance.conditions({
		{
			gate_index = 0,
			gate_key = "quality",
			alternative_index = 0,
			atom_index = 0,
			predicate = "quality",
			minimum = 11,
			maximum = 14,
			phase = "operation_input",
		},
	})
	contains(quality, 'data-erenshor-predicate="quality"')
	local formulaCases = {
		{ "selected_fuel_level_plus_one", "operation_outcome" },
		{ "matching_input_quality", "operation_input" },
		{ "all_offered_slots_consumed", "mechanic_parameter" },
		{ "return_original_equipment_quality", "operation_outcome" },
		{ "max_quality_minus_ten_or_zero", "mechanic_parameter" },
		{ "integer_roll_0_99_lt_pair_chance_plus_improvement_bonus", "operation_outcome" },
		{
			"improved_input_and_second_integer_roll_0_99_lt_bonus_plus_pair_enhancement",
			"operation_outcome",
		},
	}
	for _, case in ipairs(formulaCases) do
		local shown = Provenance.parameters({
			{
				gate_key = "operation",
				parameter_index = 0,
				predicate = "formula_operand",
				value = case[1],
				phase = case[2],
			},
		})
		if shown == "" then
			error("Canonical operation formula disappeared")
		end
	end
	local byproduct = {
		source_key = "byproduct-fixture",
		item_stable_key = "item:bear_pelt",
		kind = "crafting",
		source_stable_key = "item:bear_meat",
		mechanic = "remove_blessing",
		variant_key = "blessing_removal_byproduct",
		probability_kind = "not_applicable",
		quantity_kind = "exact",
		quantity_min = 1,
		quantity_max = 1,
	}
	local operation = Provenance.render({
		references = REFERENCES,
		sources = { byproduct },
		usages = {
			{
				use_key = "removal-fixture",
				item_stable_key = "item:bear_meat",
				target_stable_key = "item:bear_meat",
				kind = "smithing",
				mechanic = "remove_blessing",
				outcome_key = "byproduct-fixture",
				quantity_kind = "exact",
				quantity_min = 1,
				quantity_max = 1,
			},
		},
	}, function()
		return byproduct, REFERENCES
	end)
	contains(operation, "From removing a blessing")
	absent(operation, "Crafted with")
	contains(operation, "Remove a blessing with")
	contains(operation, "Produces:")
	contains(operation, "Bear Pelt")
	for _, itemKind in ipairs({ "weapon", "armor" }) do
		local equipment = Provenance.render({
			references = REFERENCES,
			usages = {
				{
					use_key = "equipment-smithing",
					kind = "smithing",
					target_stable_key = "item:bear_meat",
					outcome_key = "byproduct-fixture",
				},
				{
					use_key = "equipment-offering",
					kind = "quality_offering",
					target_stable_key = "item:bear_meat",
				},
				{
					use_key = "equipment-second-smithing",
					kind = "smithing",
					target_stable_key = "item:bear_meat",
				},
				{
					use_key = "equipment-crafting",
					kind = "crafting_material",
					target_stable_key = "item:bear_meat",
				},
			},
		}, function()
			error("A quality summary must not resolve individual operation outcomes")
		end, itemKind)
		if count(equipment, "[[Item Quality|Quality upgrades]]") ~= 1 then
			error("Equipment must show one quality upgrades link")
		end
		absent(equipment, "Quality offering")
		absent(equipment, "Smithing")
		absent(equipment, "Produces:")
		contains(equipment, 'data-erenshor-use-key="equipment-crafting"')
		contains(equipment, "Crafting material for")
		contains(equipment, "Bear Meat")
	end
	local exactOutcome = ItemData.outcome({
		target_stable_key = "item:magical_bag",
		outcome_key = "acq:fixture-yield",
	})
	if exactOutcome.item_stable_key ~= "item:ember_longsword" then
		error("Outcome lookup assumed its material target")
	end
	local unknownOutcome = pcall(
		ItemData.outcome,
		{ target_stable_key = "item:ember_longsword", outcome_key = "missing-outcome" }
	)
	if unknownOutcome then
		error("Unknown outcome must not fall back to a target item")
	end
	return "PASS Erenshor ItemData testcases"
end

return p
