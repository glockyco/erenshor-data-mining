local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")
local Quality = require("Module:Erenshor/Item/Quality")

local p = {}
local IDENTITY_ATTRIBUTES = {
	["data-erenshor-reference"] = true,
	["data-erenshor-reference-slot"] = true,
	["data-erenshor-scope"] = true,
	["data-erenshor-location"] = true,
	["data-erenshor-gate-scope"] = true,
	["data-erenshor-entry-zone-lines"] = true,
	["data-erenshor-provenance"] = true,
	["data-erenshor-acquisition-members"] = true,
	["data-erenshor-source-copy-stable-key"] = true,
}

local function preserveIdentities(html)
	return Format.preserveIdentityAttributes(html, IDENTITY_ATTRIBUTES)
end
local LABELS = {
	character_drop = "Dropped by",
	common_world_item = "World drop",
	special_world_drop = "World drop",
	vendor = "Sold by",
	dialog = "Given by",
	quest_reward = "Reward from",
	crafting = "Crafted with",
	item_drop = "Obtained by using",
	spell_created = "Created by",
	mining = "Mined in",
	fishing = "Fished in",
	fishing_bonus = "Fishing reward",
	auction_house = "Auction House",
	item_bag = "Picked up in",
	starting_class = "Starting item of",
	ui_grant = "Obtained from",
	item_conversion = "Item exchange",
	crafting_material = "Crafting material for",
	crafting_recipe = "Recipe for",
	quest_requirement = "Required for",
	smithing = "Smithing",
	quality_offering = "Quality offering",
	zone_restriction = "Zone restriction",
}
local USE_LABELS =
	{ item_drop = "Can yield", spell_created = "Creates", item_conversion = "Converts to" }
local PREDICATES = {
	quest_done = "After completing",
	quest_not_done = "Before completing",
	item_held = "Requires",
	key_held = "Requires key",
	room_furnished = "Requires furnished room",
	encounter_won = "After defeating",
	never = "Unavailable",
	time_of_day = "Time",
	actor_level = "Level",
	actor_class = "Class",
	item_not_owned = "Only while not owning",
	source_replenishment = "Replenishes while open",
	route = "Route",
	quality = "Quality",
	zone_use = "When used in",
	formula_operand = "Chance",
}
local BASES = {
	per_kill = "per kill",
	per_successful_catch = "per successful catch",
	per_node = "per node",
	per_use = "per use",
	per_listing_opportunity = "",
}
local LOCATIONS = {
	fixed = "",
	spawn = "",
	possible_treasure = "Possible treasure location",
	interaction = "",
	mechanic_zone = "",
	unlocated = "Location varies",
}
local NATIVE_SOURCES = { cosmetic_panel = "Cosmetic panel", planning_table = "Planning table" }
local FORMULAS = {
	chance_per_stone_pair = "Chance per stone pair",
	chance_per_improvement_level = "Chance per improvement level",
	enhance_chance_per_stone_pair = "Enhancement chance per stone pair",
	normal_to_11_else_plus_1 = "Standard items become Improved +1. Matching Improved items gain one level",
	selected_fuel_level_plus_one = "Result quality follows the selected fuel",
	fuel_level = "Fuel level",
	matching_input_quality = "Matching input qualities",
	equal_positive_stone_counts = "Equal-sized stacks of both stones",
	all_offered_slots_consumed = "All offered stacks are used in the exchange",
	return_original_equipment_quality = "On failure, the gear is returned at its original quality",
	max_quality_minus_ten_or_zero = "The improvement bonus uses the gear's Improved level, or zero for Standard gear",
	integer_roll_0_99_lt_pair_chance_plus_improvement_bonus = "Success uses the stone-pair chance plus the improvement bonus",
	improved_input_and_second_integer_roll_0_99_lt_bonus_plus_pair_enhancement = "Improved gear uses a second roll for the enhanced quality: improvement bonus plus stone-pair enhancement chance",
}
local PERCENT_FORMULAS = {
	chance_per_stone_pair = true,
	chance_per_improvement_level = true,
	enhance_chance_per_stone_pair = true,
}
local QUALITY_ORDER = Quality.list(true)
local SMITHING_LABELS = {
	forge_fuel = "Fuel for",
	blessing_removal_fuel = "Fuel for blessing removal",
	combining_fuel = "Fuel for combining",
	upgrade_material = "Upgrade material",
	blessing_removal_material = "Blessing removal material",
	combine_quality = "Combining material",
	quality_upgrade = "Upgrade quality with",
	remove_blessing = "Remove a blessing with",
	combine_matching = "Combine matching items with",
}
local QUALITY_NAMES = {
	normal = "Standard",
	standard = "Standard",
	blessed = "Blessed",
	divine = "Ascended",
	ascended = "Ascended",
	matching = "Matching qualities",
}
for _, quality in ipairs(QUALITY_ORDER) do
	QUALITY_NAMES[tostring(quality.runtimeId)] = quality.name
	QUALITY_NAMES[string.lower(quality.name)] = quality.name
end

local function public(row)
	return row.player_access_state == "verified_player" and row.probability_stage ~= "native_pool"
end

local function auditDisposition(row)
	return row.probability_stage == "native_pool" and "native_pool" or row.player_access_state
end

local function words(v)
	return tostring(v or ""):gsub("_", " ")
end

local function escape(v)
	return Format.escape(tostring(v or "")):gsub('"', "&quot;")
end

local function number(v)
	return string.format("%.12g", v)
end

local function identity(key, references)
	if key == nil or key == "" then
		return ""
	end
	local prefix = tostring(key):match("^([^:]+):")
	local kind = ({ spell = "ability", skill = "ability", stance = "ability" })[prefix] or prefix
	if
		kind == "item"
		or kind == "ability"
		or kind == "character"
		or kind == "quest"
		or kind == "zone"
		or kind == "class"
		or kind == "faction"
	then
		local reference = references and references[key]
		if
			type(reference) ~= "table"
			or reference.key ~= key
			or type(reference.name) ~= "string"
			or reference.name == ""
			or (
				reference.page ~= nil and (type(reference.page) ~= "string" or reference.page == "")
			)
		then
			error("Missing or invalid native ItemData reference: " .. tostring(key), 2)
		end
		if reference.page ~= nil then
			return Link.render({ kind = kind, stablekey = key })
		end
		return Format.escape(reference.name)
	end
	return ""
end

local function interval(minimum, maximum)
	if minimum == nil and maximum == nil then
		return ""
	end
	if maximum == minimum then
		return number(minimum)
	end
	if maximum == nil then
		return "at least " .. number(minimum)
	end
	if minimum == nil then
		return "up to " .. number(maximum)
	end
	return number(minimum) .. " to " .. number(maximum)
end

local function qualityRange(condition)
	local names, improved = {}, true
	for _, quality in ipairs(QUALITY_ORDER) do
		local id = quality.runtimeId
		local above = condition.minimum == nil
			or id > condition.minimum
			or (id == condition.minimum and condition.minimum_inclusive ~= false)
		local below = condition.maximum == nil
			or id < condition.maximum
			or (id == condition.maximum and condition.maximum_inclusive ~= false)
		if above and below then
			names[#names + 1] = quality.name
			improved = improved and Quality.isImproved(quality.name)
		end
	end
	if #names == 0 then
		error("Unsupported ItemData quality bounds", 2)
	end
	if #names == #QUALITY_ORDER then
		return "Any quality"
	end
	if #names == 1 then
		return names[1]
	end
	if improved then
		if #names == 5 then
			return "Improved"
		end
		return names[1] .. " to " .. names[#names]
	end
	return table.concat(names, " or ")
end

local function conditionRange(condition)
	local minimum, maximum = condition.minimum, condition.maximum
	if minimum == nil and maximum == nil then
		return ""
	end
	if condition.predicate == "quality" then
		return qualityRange(condition)
	end
	if condition.predicate == "formula_operand" then
		if condition.value == "equal_positive_stone_counts" then
			return interval(minimum, maximum) .. " each"
		end
		if condition.value == "normal_to_11_else_plus_1" then
			local quality = maximum and QUALITY_NAMES[tostring(maximum)]
			return quality and ("up to " .. quality) or ""
		end
		if PERCENT_FORMULAS[condition.value] or condition.value == "fuel_level" then
			return number(minimum or maximum)
		end
		return ""
	end
	if minimum == maximum then
		return number(minimum)
	end
	if minimum == nil then
		return (condition.maximum_inclusive == false and "below " or "at most ") .. number(maximum)
	end
	if maximum == nil then
		return (condition.minimum_inclusive == false and "above " or "at least ") .. number(minimum)
	end
	return (condition.minimum_inclusive == false and "above " or "")
		.. number(minimum)
		.. " to "
		.. (condition.maximum_inclusive == false and "below " or "")
		.. number(maximum)
end

local PHASE_GROUPS = {
	availability = "requirements",
	operation_input = "requirements",
	source_initialization = "initialization",
	operation_outcome = "outcomes",
	mechanic_parameter = "parameters",
}
local OWNERSHIP_PREDICATES = { item_held = true, item_not_owned = true, key_held = true }

local function accountConditionText(condition)
	if
		condition.actor ~= "account"
		or condition.reference_stable_key ~= "account_state:reliquary_claimed"
		or (condition.value ~= "true" and condition.value ~= "false")
		or (condition.phase ~= "availability" and condition.phase ~= "operation_outcome")
	then
		error("Unsupported ItemData account condition", 2)
	end
	return "Reliquary Hall "
		.. (condition.value == "true" and "claimed" or "unclaimed")
		.. " on this account"
end

function p.conditions(rows, references)
	local gates, gateOrder, gateGroups = {}, {}, {}
	for _, condition in ipairs(rows or {}) do
		local phase = condition.phase
		local category = PHASE_GROUPS[phase]
		if category == nil then
			error("Unsupported ItemData condition phase: " .. tostring(phase), 2)
		end
		if
			not (
				phase == "source_initialization"
				and (
					OWNERSHIP_PREDICATES[condition.predicate]
					or condition.predicate == "formula_operand"
				)
			)
		then
			local gate = phase .. "\0" .. condition.gate_key
			if gates[gate] == nil then
				gates[gate] = {}
				gateGroups[gate] = category
				gateOrder[#gateOrder + 1] = gate
			end
			local groups = gates[gate]
			local index = condition.group_index
			if groups[index] == nil then
				groups[index] = {}
			end
			groups[index][#groups[index] + 1] = condition
		end
	end
	local out = { requirements = {}, initialization = {}, outcomes = {}, parameters = {} }
	for _, gate in ipairs(gateOrder) do
		local indices = {}
		for index in pairs(gates[gate]) do
			indices[#indices + 1] = index
		end
		table.sort(indices)
		local alternatives = {}
		for _, index in ipairs(indices) do
			local atoms = gates[gate][index]
			table.sort(atoms, function(a, b)
				return a.atom_index < b.atom_index
			end)
			local parts = {}
			for _, condition in ipairs(atoms) do
				local account = condition.predicate == "account_state"
				local text = account and accountConditionText(condition)
					or PREDICATES[condition.predicate]
				if text == nil then
					error("Unsupported ItemData condition: " .. tostring(condition.predicate), 2)
				end
				if condition.gate_key == "result_quality" and not account then
					text = "Result quality"
				end
				if condition.gate_key == "enhanced_quality" and not account then
					text = "Improved result quality"
				end
				if condition.reference_stable_key and not account then
					text = text .. ": " .. identity(condition.reference_stable_key, references)
				end
				if
					condition.predicate == "room_furnished"
					and condition.reference_slot
					and condition.reference_slot ~= ""
				then
					text = text .. " (room " .. escape(condition.reference_slot) .. ")"
				end
				if condition.predicate == "actor_level" then
					text = (
						({ player = "Player", sim = "Simulated player", enemy = "Enemy" })[condition.actor]
						or escape(words(condition.actor))
					) .. " level"
				elseif condition.predicate == "actor_class" then
					local actor = ({ player = "Player", sim = "Simulated player", enemy = "Enemy" })[condition.actor]
					if actor == nil then
						error("Unsupported ItemData class actor: " .. tostring(condition.actor), 2)
					end
					text = actor .. " class"
					if condition.reference_stable_key then
						text = text .. ": " .. identity(condition.reference_stable_key, references)
					end
				elseif condition.actor and not account then
					text = text .. " for " .. escape(words(condition.actor))
				end
				if condition.predicate == "formula_operand" then
					text = FORMULAS[condition.value]
					if text == nil then
						error("Unsupported ItemData formula: " .. tostring(condition.value), 2)
					end
				elseif
					condition.predicate == "route"
					and condition.value == "normal_pointer_inventory_transfer"
				then
					text = "Drag into your inventory"
				elseif
					condition.predicate == "source_replenishment"
					and condition.value == "while_source_active"
				then
					text = "Replenishes while open"
				elseif condition.predicate == "quality" and condition.value then
					local quality = QUALITY_NAMES[string.lower(condition.value)]
					if quality == nil then
						error("Unsupported ItemData quality: " .. tostring(condition.value), 2)
					end
					text = text .. ": " .. quality
				elseif condition.predicate == "room_furnished" and condition.value then
					text = text .. ": " .. escape(condition.value)
				elseif condition.value and not account then
					if condition.predicate ~= "time_of_day" then
						error(
							"Unsupported ItemData condition value: "
								.. tostring(condition.predicate),
							2
						)
					end
					text = condition.value == "day" and "During the day"
						or condition.value == "night" and "At night"
						or error("Unsupported ItemData time", 2)
				end
				local range = account and "" or conditionRange(condition)
				if range ~= "" then
					text = text .. " " .. range
					if PERCENT_FORMULAS[condition.value] then
						text = text .. "%"
					end
				end
				parts[#parts + 1] = '<span data-erenshor-predicate="'
					.. escape(condition.predicate)
					.. '" data-erenshor-phase="'
					.. escape(condition.phase)
					.. '" data-erenshor-scope="'
					.. escape(condition.scope)
					.. '" data-erenshor-reference="'
					.. escape(condition.reference_stable_key)
					.. '" data-erenshor-reference-slot="'
					.. escape(condition.reference_slot)
					.. '">'
					.. text
					.. "</span>"
			end
			alternatives[#alternatives + 1] = "(" .. table.concat(parts, " and ") .. ")"
		end
		local bucket = out[gateGroups[gate]]
		local gateText = table.concat(alternatives, " or ")
		bucket[#bucket + 1] = #alternatives > 1 and ("(" .. gateText .. ")") or gateText
	end
	local rendered = {}
	if #out.requirements > 0 then
		rendered[#rendered + 1] = table.concat(out.requirements, " and ")
	end
	for _, section in ipairs({
		{ "initialization", "Source" },
		{ "outcomes", "Result" },
		{ "parameters", "Mechanics" },
	}) do
		local entries = out[section[1]]
		if #entries > 0 then
			rendered[#rendered + 1] = section[2] .. ": " .. table.concat(entries, " and ")
		end
	end
	return preserveIdentities(table.concat(rendered, "<br />"))
end

local function locations(rows, references)
	local out = {}
	for _, location in ipairs(rows or {}) do
		local parts = {}
		if location.source_copy_stable_key then
			parts[#parts + 1] = identity(location.source_copy_stable_key, references)
		end
		if location.zone_stable_key then
			parts[#parts + 1] = identity(location.zone_stable_key, references)
		elseif location.scene then
			parts[#parts + 1] = escape(location.scene)
		end
		if location.relation then
			local label = LOCATIONS[location.relation]
			if label == nil then
				error("Unsupported ItemData location: " .. tostring(location.relation), 2)
			end
			if label ~= "" then
				parts[#parts + 1] = label
			end
		end
		if location.x ~= nil and location.y ~= nil and location.z ~= nil then
			parts[#parts + 1] = "("
				.. number(location.x)
				.. ", "
				.. number(location.y)
				.. ", "
				.. number(location.z)
				.. ")"
		end
		local levels = interval(location.player_level_min, location.player_level_max)
		if levels ~= "" then
			parts[#parts + 1] = "player level " .. levels
		end
		local conditions = p.conditions(location.conditions, references)
		if conditions ~= "" then
			parts[#parts + 1] = conditions
		end
		local entries = {}
		for _, key in ipairs(location.entry_zone_line_keys or {}) do
			entries[#entries + 1] = key
		end
		local entryKeys = table.concat(entries, "|")
		out[#out + 1] = '<span data-erenshor-location="'
			.. escape(location.location_key)
			.. '" data-erenshor-source-copy-stable-key="'
			.. escape(location.source_copy_stable_key)
			.. '" data-erenshor-gate-scope="'
			.. escape(location.gate_scope)
			.. '" data-erenshor-entry-zone-lines="'
			.. escape(entryKeys)
			.. '">'
			.. table.concat(parts, ", ")
			.. "</span>"
	end
	return table.concat(out, "<br />")
end

local function facts(row, references)
	local parts = {}
	local amount = interval(row.quantity_min, row.quantity_max)
	if amount ~= "" then
		parts[#parts + 1] = "Quantity: " .. amount
	end
	if row.quantity_kind == "bounded" then
		parts[#parts + 1] = "quantity varies"
	end
	if row.expected_quantity ~= nil then
		parts[#parts + 1] = "Average yield: " .. number(row.expected_quantity)
	end
	if row.count_distribution then
		local distribution = mw.text.jsonDecode(row.count_distribution)
		local isArray = row.count_distribution:match("^%s*%[") ~= nil
		local counts = {}
		for key, chance in pairs(distribution) do
			local count = tonumber(key)
			if count ~= nil and isArray then
				count = count - 1
			end
			if
				count == nil
				or count < 0
				or count ~= math.floor(count)
				or type(chance) ~= "number"
				or chance < 0
				or chance > 1
			then
				error("Unsupported ItemData count distribution", 2)
			end
			counts[#counts + 1] = { count = count, chance = chance, key = tostring(key) }
		end
		if #counts == 0 then
			error("Empty ItemData count distribution", 2)
		end
		table.sort(counts, function(a, b)
			return a.count < b.count or (a.count == b.count and a.key < b.key)
		end)
		local outcomes = {}
		for _, outcome in ipairs(counts) do
			outcomes[#outcomes + 1] = number(outcome.count)
				.. " ("
				.. number(outcome.chance * 100)
				.. "%)"
		end
		parts[#parts + 1] = "Yield: " .. table.concat(outcomes, ", ")
	end
	if row.probability_kind == "exact" or row.probability_kind == "bounded" then
		local chance = interval(row.probability_min, row.probability_max)
		parts[#parts + 1] = "Chance: " .. chance .. "%"
	end
	if BASES[row.probability_basis] and BASES[row.probability_basis] ~= "" then
		parts[#parts + 1] = BASES[row.probability_basis]
	end
	if row.guarantee_scope == "pool" or row.guarantee_scope == "pool_roll" then
		parts[#parts + 1] = row.guaranteed_roll_count
				and ("Guaranteed pool rolls: " .. tostring(row.guaranteed_roll_count))
			or "Guaranteed pool roll"
	elseif row.guarantee_scope == "item" then
		parts[#parts + 1] = "Guaranteed item"
	elseif row.guarantee_scope == "successful_roll" then
		parts[#parts + 1] = "Guaranteed after a successful roll"
	elseif row.guarantee_scope == "successful_ui_transfer" then
		parts[#parts + 1] = "Available from the panel"
	elseif row.guarantee_scope then
		error("Unsupported ItemData guarantee: " .. tostring(row.guarantee_scope), 2)
	end
	if row.kind == "zone_restriction" and row.mechanic then
		parts[#parts + 1] = "Outcome: " .. escape(words(row.mechanic))
	end
	local conditions = p.conditions(row.conditions, references)
	if conditions ~= "" then
		parts[#parts + 1] = conditions
	end
	local place = locations(row.locations, references)
	if place ~= "" then
		parts[#parts + 1] = place
	end
	return table.concat(parts, "<br />")
end

function p.acquisitionDetails(row, references)
	return preserveIdentities(facts(row, references))
end

function p.locations(rows, references)
	return preserveIdentities(locations(rows, references))
end

local function globalFishing(data)
	local bonus, members = nil, {}
	for _, row in ipairs(data.acquisitions or {}) do
		if row.kind == "fishing_bonus" and row.probability_stage == "native_pool" then
			if bonus ~= nil or row.probability_min ~= row.probability_max then
				return nil, {}
			end
			bonus = row.probability_min
		end
	end
	if bonus == nil then
		return nil, members
	end
	for _, row in ipairs(data.acquisitions or {}) do
		if
			public(row)
			and row.kind == "fishing"
			and row.probability_min == bonus
			and row.probability_max == bonus
		then
			members[row.acquisition_key] = true
		end
	end
	return bonus, members
end

-- Coverage is a machine-readable audit, never a claim that an internal route gives an item to players.
function p.coverage(data, resolveOutcome)
	local out = {}
	local _, grouped = globalFishing(data)
	for _, row in ipairs(data.acquisitions or {}) do
		out[row.acquisition_key] = grouped[row.acquisition_key] and "grouped_global_fishing"
			or (public(row) and "rendered" or auditDisposition(row))
	end
	for _, row in ipairs(data.uses or {}) do
		if row.outcome_key and resolveOutcome == nil then
			error("ItemData coverage requires canonical outcome resolver", 2)
		end
		local outcome = row.outcome_key and resolveOutcome(row)
		out[row.use_key] = outcome and not public(outcome) and auditDisposition(outcome)
			or "rendered"
	end
	return out
end

function p.covered(data, item, kind, source)
	for _, row in ipairs(data.acquisitions or {}) do
		if
			row.item_stable_key == item
			and row.kind == kind
			and row.source_stable_key == source
			and public(row)
		then
			return true
		end
	end
	return false
end

function p.render(data, resolveOutcome)
	local rows = {}
	local function put(row, isUse, outcome, outcomeReferences)
		local key = isUse and row.use_key or row.acquisition_key
		local target = isUse and row.target_stable_key or row.source_stable_key
		local source = identity(target, data.references)
		if row.kind == "special_world_drop" then
			source = "Any enemy"
		elseif row.kind == "common_world_item" then
			source = "Any enemy with common drops"
		elseif source == "" then
			source = LABELS[row.kind]
				or error("Unsupported ItemData relationship: " .. tostring(row.kind), 2)
		end
		if row.kind == "ui_grant" then
			source = NATIVE_SOURCES[row.mechanic]
			if source == nil then
				error("Unknown ItemData interface mechanic: " .. tostring(row.mechanic), 2)
			end
		end
		if row.kind == "auction_house" then
			source = "May be listed by simulated players"
		end
		local attributes = ' data-erenshor-provenance="'
			.. escape(key)
			.. '" data-erenshor-'
			.. (isUse and "use-key" or "acquisition-key")
			.. '="'
			.. escape(key)
			.. '"'
		attributes = attributes
			.. " data-erenshor-"
			.. (isUse and "target-key" or "source-key")
			.. '="'
			.. escape(target)
			.. '"'
		for _, field in ipairs({
			"source_group_key",
			"source_copy_stable_key",
			"variant_key",
			"outcome_key",
			"material_slot",
			"mechanic",
		}) do
			if row[field] ~= nil then
				attributes = attributes
					.. " data-erenshor-"
					.. field:gsub("_", "-")
					.. '="'
					.. escape(row[field])
					.. '"'
			end
		end
		local details = facts(row, data.references)
		if row.kind == "special_world_drop" then
			details = details .. "<br />At the default loot rate."
		end
		if outcome then
			local produced = ""
			if outcome.item_stable_key ~= row.target_stable_key then
				produced = "Produces: "
					.. identity(outcome.item_stable_key, outcomeReferences)
					.. "<br />"
			end
			details = details
				.. '<div class="item-data-outcome" data-erenshor-outcome-key="'
				.. escape(outcome.acquisition_key)
				.. '">'
				.. produced
				.. facts(outcome, outcomeReferences)
				.. "</div>"
		end
		local label = (isUse and USE_LABELS[row.kind])
			or LABELS[row.kind]
			or escape(words(row.kind))
		if
			row.kind == "crafting"
			and row.mechanic == "remove_blessing"
			and row.variant_key == "blessing_removal_byproduct"
		then
			label = "From removing a blessing"
		elseif isUse and row.kind == "smithing" then
			label = SMITHING_LABELS[row.mechanic] or label
		end
		rows[#rows + 1] = "<tr"
			.. attributes
			.. '><th scope="row">'
			.. label
			.. "</th><td>"
			.. source
			.. "</td><td>"
			.. details
			.. "</td></tr>"
	end
	local audit = {}
	local bonus, grouped = globalFishing(data)
	local groupKeys = {}
	for key in pairs(grouped) do
		groupKeys[#groupKeys + 1] = key
	end
	table.sort(groupKeys)
	if #groupKeys > 0 then
		rows[#rows + 1] = '<tr data-erenshor-acquisition-members="'
			.. escape(mw.text.jsonEncode(groupKeys))
			.. '"><th scope="row">Fished in</th><td>Any water</td><td>Chance: '
			.. number(bonus)
			.. "% per successful catch</td></tr>"
	end
	local function auditOnly(key, isUse, reason)
		audit[#audit + 1] = '<span hidden="hidden" style="display:none" data-erenshor-'
			.. (isUse and "use-key" or "acquisition-key")
			.. '="'
			.. escape(key)
			.. '" data-erenshor-disposition="'
			.. escape(reason)
			.. '"></span>'
	end
	for _, row in ipairs(data.acquisitions or {}) do
		if grouped[row.acquisition_key] then
			auditOnly(row.acquisition_key, false, "grouped_global_fishing")
		elseif public(row) then
			put(row, false)
		else
			auditOnly(row.acquisition_key, false, auditDisposition(row))
		end
	end
	for _, row in ipairs(data.uses or {}) do
		local outcome, outcomeReferences
		if row.outcome_key then
			if resolveOutcome == nil then
				error("ItemData use requires canonical outcome resolver", 2)
			end
			outcome, outcomeReferences = resolveOutcome(row)
		end
		if outcome and not public(outcome) then
			auditOnly(row.use_key, true, auditDisposition(outcome))
		else
			put(row, true, outcome, outcomeReferences)
		end
	end
	local rendered = ""
	if #rows > 0 then
		rendered = '\n<div class="item-data-provenance"><h2>Sources and uses</h2><table class="wikitable"><tr><th>Relationship</th><th>Source or use</th><th>Details</th></tr>'
			.. table.concat(rows, "\n")
			.. "</table></div>"
	end
	return preserveIdentities(rendered .. table.concat(audit, ""))
end

p.identity = identity

return p
