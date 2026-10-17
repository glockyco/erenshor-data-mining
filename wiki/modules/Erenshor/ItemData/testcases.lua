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
		for _, acquisition in ipairs(relation.acquisitions) do
			if acquisition.acquisition_key ~= split.fact then
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
		acquisitions = {
			{
				acquisition_key = "acquisition:native-reference",
				kind = "character_drop",
				source_stable_key = copy,
				source_copy_stable_key = copy,
				player_access_state = "verified_player",
				conditions = {
					{
						gate_key = "native-quest",
						group_index = 0,
						atom_index = 0,
						phase = "availability",
						predicate = "quest_done",
						reference_stable_key = quest,
					},
				},
				locations = {
					{
						location_key = "location:native-reference",
						relation = "fixed",
						source_copy_stable_key = copy,
						zone_stable_key = "zone:PortAzure",
						conditions = {
							{
								gate_key = "local-quest",
								group_index = 0,
								atom_index = 0,
								phase = "availability",
								predicate = "quest_not_done",
								reference_stable_key = target,
							},
						},
					},
				},
			},
		},
		uses = {
			{
				use_key = "use:native-reference",
				kind = "quest_requirement",
				target_stable_key = target,
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
		contains(rendered, 'data-erenshor-acquisition-key="' .. key .. '"')
	end
	contains(rendered, 'data-erenshor-use-key="use:bag-recipe"')
	contains(rendered, 'data-erenshor-use-key="use:bag-yield"')
	contains(rendered, 'data-erenshor-outcome-key="acq:fixture-yield"')
	contains(rendered, "12.5%")
	contains(rendered, "Guaranteed pool rolls: 2")
	contains(rendered, "1.25e-06%")
	contains(rendered, "1.25 to 7.5%")
	contains(rendered, "Requires furnished room")
	contains(rendered, "10 to below 20")
	contains(rendered, "Location varies")
	contains(rendered, "May be listed by simulated players")
	contains(rendered, 'data-erenshor-disposition="internal_only"')
	contains(rendered, 'data-erenshor-disposition="unconfirmed_player"')
	contains(rendered, 'data-erenshor-disposition="native_pool"')
	absent(rendered, "secret_table")
	absent(rendered, "secret-fixture")
	local coverage = Provenance.coverage(data, ItemData.outcome)
	if coverage["acq:bag-day"] ~= "rendered" or coverage["acq:bag-internal"] ~= "internal_only" then
		error("Canonical coverage audit changed")
	end
	local global = Provenance.render({
		acquisitions = {
			{
				acquisition_key = "bonus",
				kind = "fishing_bonus",
				probability_stage = "native_pool",
				probability_min = 1.25,
				probability_max = 1.25,
			},
			{
				acquisition_key = "water:day",
				kind = "fishing",
				player_access_state = "verified_player",
				probability_kind = "exact",
				probability_min = 1.25,
				probability_max = 1.25,
			},
			{
				acquisition_key = "water:night",
				kind = "fishing",
				player_access_state = "verified_player",
				probability_kind = "exact",
				probability_min = 1.25,
				probability_max = 1.25,
			},
			{
				acquisition_key = "water:enhanced",
				kind = "fishing",
				player_access_state = "verified_player",
				probability_kind = "exact",
				probability_min = 7.1875,
				probability_max = 7.1875,
			},
		},
		uses = {},
	})
	if count(global, "Any water") ~= 1 then
		error("Global fishing must render one summary")
	end
	contains(global, "1.25% per successful catch")
	contains(global, "7.1875%")
	contains(global, 'data-erenshor-acquisition-key="water:day"')
	contains(global, 'data-erenshor-acquisition-key="water:night"')
	contains(global, 'data-erenshor-acquisition-key="water:enhanced"')
	contains(global, 'data-erenshor-disposition="grouped_global_fishing"')
	local phased = Provenance.conditions({
		{
			gate_key = "ownership",
			group_index = 0,
			atom_index = 0,
			phase = "source_initialization",
			predicate = "item_not_owned",
			reference_stable_key = "item:magical_bag",
		},
		{
			gate_key = "input",
			group_index = 0,
			atom_index = 0,
			phase = "operation_input",
			predicate = "item_held",
			reference_stable_key = "item:copper_armor_mold",
			minimum = 1,
		},
		{
			gate_key = "output",
			group_index = 0,
			atom_index = 0,
			phase = "operation_outcome",
			predicate = "quality",
			value = "blessed",
		},
		{
			gate_key = "chance",
			group_index = 0,
			atom_index = 0,
			phase = "mechanic_parameter",
			predicate = "formula_operand",
			value = "chance_per_stone_pair",
			minimum = 40,
		},
	}, REFERENCES)
	absent(phased, "Only while not owning")
	contains(phased, 'data-erenshor-phase="operation_input"')
	contains(phased, 'data-erenshor-phase="operation_outcome"')
	contains(phased, "Result:")
	contains(phased, "Mechanics:")
	contains(phased, "40%")
	local bounded = Provenance.render({
		acquisitions = {
			{
				acquisition_key = "bounded",
				kind = "vendor",
				player_access_state = "verified_player",
				probability_kind = "not_applicable",
				quantity_kind = "bounded",
				quantity_min = 1,
			},
		},
		uses = {},
	})
	contains(bounded, "Quantity: at least 1")
	local unknown = Provenance.render({
		acquisitions = {
			{
				acquisition_key = "unknown",
				kind = "vendor",
				player_access_state = "verified_player",
				probability_kind = "unknown",
				quantity_kind = "unknown",
			},
		},
		uses = {},
	})
	absent(unknown, "Quantity:")
	local class = Provenance.conditions({
		{
			gate_key = "class",
			group_index = 0,
			atom_index = 0,
			phase = "availability",
			predicate = "actor_class",
			actor = "player",
			reference_stable_key = "class:paladin",
		},
	}, REFERENCES)
	contains(class, "Player class")
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
			{ location_key = "formatter-fixture", relation = "unlocated", conditions = {} },
		}),
		"Location varies"
	)
	contains(
		Provenance.acquisitionDetails({ count_distribution = '{"2":0.25,"0":0.75}' }),
		"Yield: 0 (75%), 2 (25%)"
	)
	contains(
		Provenance.acquisitionDetails({ count_distribution = "[0.75,0,0.25]" }),
		"Yield: 0 (75%), 1 (0%), 2 (25%)"
	)
	local legacyDistribution = pcall(
		Provenance.acquisitionDetails,
		{ count_distribution = '[{"Count":0,"Chance":"75%"}]' }
	)
	if legacyDistribution then
		error("Legacy count objects are not the canonical distribution contract")
	end
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
			group_index = 0,
			atom_index = 0,
			phase = "availability",
			predicate = "time_of_day",
			value = "day",
		},
		{
			gate_key = "time",
			group_index = 1,
			atom_index = 0,
			phase = "availability",
			predicate = "time_of_day",
			value = "night",
		},
		{
			gate_key = "level",
			group_index = 0,
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
			group_index = 0,
			atom_index = 0,
			predicate = "account_state",
			actor = "account",
			reference_stable_key = "account_state:reliquary_claimed",
			value = "false",
			phase = "availability",
			scope = "claim-location",
		},
		{
			gate_key = "claim",
			group_index = 0,
			atom_index = 0,
			predicate = "account_state",
			actor = "account",
			reference_stable_key = "account_state:reliquary_claimed",
			value = "true",
			phase = "operation_outcome",
			scope = "claim-location",
		},
	})
	contains(account, "Reliquary Hall unclaimed on this account")
	contains(account, "Result:")
	contains(account, "Reliquary Hall claimed on this account")
	contains(account, 'data-erenshor-reference="account_state:reliquary_claimed"')
	contains(account, 'data-erenshor-scope="claim-location"')
	absent(account, "quest:")
	local questAlias = pcall(Provenance.conditions, {
		{
			gate_key = "claim",
			group_index = 0,
			atom_index = 0,
			predicate = "account_state",
			actor = "account",
			reference_stable_key = "quest:reliquary_claimed",
			value = "false",
			phase = "availability",
			scope = "claim-location",
		},
	})
	if questAlias then
		error("Account claim state must not accept a quest alias")
	end
	local outcomeAlias = pcall(Provenance.conditions, {
		{
			gate_key = "claim",
			group_index = 0,
			atom_index = 0,
			predicate = "account_state",
			actor = "account",
			reference_stable_key = "account_state:reliquary_claimed",
			value = "true",
			phase = "outcome",
			scope = "claim-location",
		},
	})
	if outcomeAlias then
		error("Account claim state must use operation_outcome, not an outcome alias")
	end
	local forge = Provenance.conditions({
		{
			gate_key = "fuel",
			group_index = 0,
			atom_index = 0,
			predicate = "formula_operand",
			value = "fuel_level",
			minimum = 0,
			maximum = 0,
			phase = "mechanic_parameter",
		},
		{
			gate_key = "counts",
			group_index = 0,
			atom_index = 0,
			predicate = "formula_operand",
			value = "equal_positive_stone_counts",
			minimum = 1,
			phase = "operation_input",
		},
		{
			gate_key = "quality",
			group_index = 0,
			atom_index = 0,
			predicate = "quality",
			minimum = 11,
			maximum = 14,
			phase = "operation_input",
		},
		{
			gate_key = "calibration",
			group_index = 0,
			atom_index = 0,
			predicate = "formula_operand",
			value = "initial_owned_unique_item_count",
			minimum = 0,
			phase = "source_initialization",
		},
	})
	contains(forge, "Fuel level 0")
	absent(forge, "Fuel level 0%")
	contains(forge, "Equal-sized stacks of both stones at least 1 each")
	absent(forge, "each%")
	contains(forge, "Improved +1 to Improved +4")
	absent(forge, "initial_owned_unique_item_count")
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
		local shown = Provenance.conditions({
			{
				gate_key = "operation",
				group_index = 0,
				atom_index = 0,
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
		acquisition_key = "byproduct-fixture",
		item_stable_key = "item:bear_pelt",
		kind = "crafting",
		source_stable_key = "item:bear_meat",
		mechanic = "remove_blessing",
		variant_key = "blessing_removal_byproduct",
		player_access_state = "verified_player",
		probability_kind = "not_applicable",
		probability_stage = "final_acquisition",
		quantity_kind = "exact",
		quantity_min = 1,
		quantity_max = 1,
	}
	local operation = Provenance.render({
		references = REFERENCES,
		acquisitions = { byproduct },
		uses = {
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
