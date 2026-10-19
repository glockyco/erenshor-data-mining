-- Resource outcomes stay separate from canonical quest routes. Dialog gates
-- belong to their own route, never to every variant sharing a page.
local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")

local p = {}
local CATEGORY = "[[Category:Pages with missing Erenshor quest data]]"

local function message(text)
	return '<span class="erenshor-missing-data">' .. Format.escape(text) .. "</span>" .. CATEGORY
end

local function questKey(args)
	local key = Args.resolve(args, "stablekey", nil)
	if key ~= nil then
		return key
	end
	local page = Args.resolve(args, "page", nil) or mw.title.getCurrentTitle().prefixedText
	local keys = Link.pageKeys("quest", page)
	if #keys == 0 then
		return nil, "No quest has the page " .. page .. ". Pass stablekey."
	end
	if #keys > 1 then
		return nil,
			"Several quests have the page "
				.. page
				.. ": "
				.. table.concat(keys, ", ")
				.. ". Pass stablekey."
	end
	return keys[1]
end

local function entity(kind, reference)
	if
		type(kind) ~= "string"
		or type(reference) ~= "table"
		or type(reference.key) ~= "string"
		or string.sub(reference.key, 1, #kind + 1) ~= kind .. ":"
		or type(reference.name) ~= "string"
		or reference.name == ""
		or (reference.page ~= nil and type(reference.page) ~= "string")
	then
		error("Invalid native " .. tostring(kind) .. " reference")
	end
	if reference.page ~= nil then
		return Link.render({ kind = kind, stablekey = reference.key })
	end
	return Format.escape(reference.name)
end

local function route(row, data)
	local source = row.source and entity(row.sourceKind, row.source) or nil
	local methods = {
		dialog = "Talk to ",
		item_read = "Read ",
		zone_entry = "Enter ",
		quest_chain = "Complete ",
		partial_turnin = "Make a partial item turn-in to ",
		item_turnin = "Turn in the required items to ",
		talk = "Talk to ",
		read = "Read ",
		zone = "Enter ",
		chain = "Complete ",
		death = "Defeat ",
		shout = "Shout to ",
	}
	local text = (methods[row.method] or "Event: ") .. (source or "")
	local note = row.note and string.gsub(row.note, "^[%w_]+%.cs %- ", "") or nil
	if row.method == "scripted" and source then
		-- A located event leads with what happens there, then its conditions.
		text = "Event in " .. source .. (note and (": " .. Format.escape(note)) or "")
		note = nil
	end
	if row.keywords then
		local label = string.find(row.keywords, ",", 1, true) and "keywords" or "keyword"
		text = text .. " (" .. label .. ': "' .. Format.escape(row.keywords) .. '")'
	end
	if row.prerequisites then
		local quests = {}
		for _, reference in ipairs(row.prerequisites) do
			table.insert(quests, entity("quest", reference))
		end
		text = text .. ". Requires completion of " .. mw.text.listToText(quests)
	end
	if row.requiredItem then
		text = text
			.. ' (<span data-erenshor-quest-condition="carried">carrying '
			.. entity("item", row.requiredItem)
			.. "</span>)"
	end
	if row.notOwnedItem then
		text = text
			.. ' (<span data-erenshor-quest-condition="not-owned">without '
			.. entity("item", row.notOwnedItem)
			.. "</span>)"
	end
	if row.blockedByQuest then
		text = text
			.. ' (<span data-erenshor-quest-condition="quest-not-completed">before completing '
			.. entity("quest", row.blockedByQuest)
			.. "</span>)"
	end
	if row.item then
		text = text
			.. ' (receive <span data-erenshor-quest-effect="dialog-reward">'
			.. tostring(row.quantity)
			.. " x "
			.. entity("item", row.item)
			.. "</span>)"
	end
	if row.sourceVariant then
		local index, count = nil, 0
		for _, sourceRow in ipairs(data[row.source.key] or {}) do
			if sourceRow.type == "variant" then
				count = count + 1
				if sourceRow.variant == row.sourceVariant then
					index = count
				end
			end
		end
		if index and count > 1 then
			text = text .. " (option " .. tostring(index) .. ")"
		end
	end
	if row.furniture then
		text = text .. " (requires " .. entity("item", row.furniture) .. ")"
	end
	if note then
		text = text .. " (" .. Format.escape(note) .. ")"
	end
	return '<span data-erenshor-quest-route="'
		.. row.type
		.. '" data-erenshor-quest-method="'
		.. row.method
		.. '">'
		.. text
		.. "</span>"
end

local ROUTE_FIELDS = {
	"method",
	"source",
	"sourceKind",
	"keywords",
	"prerequisites",
	"sourceVariant",
	"furniture",
	"note",
	"notOwnedItem",
	"blockedByQuest",
	"requiredItem",
	"item",
	"quantity",
}

-- A reference compares by its key and a list of references by its keys in order.
local function identity(value)
	if type(value) ~= "table" then
		return value
	end
	if value.key ~= nil then
		return value.key
	end
	local keys = {}
	for _, reference in ipairs(value) do
		table.insert(keys, reference.key)
	end
	return table.concat(keys, "\n")
end

local function appendRoute(routes, row, data)
	-- Compare facts before rendering, since icon strip markers differ per call.
	for _, existing in ipairs(routes.rows or {}) do
		local same = true
		for _, field in ipairs(ROUTE_FIELDS) do
			local left, right = identity(existing[field]), identity(row[field])
			if left ~= right then
				same = false
				break
			end
		end
		if same then
			return
		end
	end
	routes.rows = routes.rows or {}
	table.insert(routes.rows, row)
	table.insert(routes, route(row, data))
end

local function cell(out, label, text)
	table.insert(out, "|-")
	table.insert(out, '! scope="row" | ' .. label)
	table.insert(out, "| " .. text)
end

local function variantsAndRoutes(rows, data)
	local variants, acquisition, completion = {}, {}, {}
	for _, row in ipairs(rows) do
		if row.type == "variant" then
			table.insert(variants, row)
		elseif row.type == "acquisition" and row.variant == nil then
			appendRoute(acquisition, row, data)
		elseif row.type == "completion" and row.variant == nil then
			appendRoute(completion, row, data)
		end
	end
	return variants, acquisition, completion
end

local function effect(kind, text)
	return '<span data-erenshor-quest-effect="' .. kind .. '">' .. text .. "</span>"
end

local function variantPanel(out, variant, rows, option, data)
	if option then
		table.insert(out, "|-")
		table.insert(out, '! colspan="2" | Option ' .. tostring(option))
	end
	local required, factions, completes, acquisition, completion = {}, {}, {}, {}, {}
	local hasDialogReward, hasOtherCompletion = false, false
	for _, row in ipairs(rows) do
		if row.type == "completion" and (row.variant == nil or row.variant == variant.variant) then
			hasDialogReward = hasDialogReward or row.item ~= nil
			hasOtherCompletion = hasOtherCompletion or row.method ~= "item_turnin"
		end
		if row.variant == variant.variant then
			if row.type == "required" then
				table.insert(required, tostring(row.quantity) .. " x " .. entity("item", row.item))
			elseif row.type == "faction" then
				local amount = row.amount > 0 and "+" .. tostring(row.amount)
					or tostring(row.amount)
				table.insert(factions, entity("faction", row.faction) .. " " .. amount)
			elseif row.type == "completes" then
				table.insert(completes, entity("quest", row.quest))
			elseif row.type == "acquisition" then
				appendRoute(acquisition, row, data)
			elseif row.type == "completion" then
				appendRoute(completion, row, data)
			end
		end
	end
	if #acquisition > 0 then
		cell(out, "Start", table.concat(acquisition, "<br>or "))
	end
	if #completion > 0 then
		cell(out, "Turn in", table.concat(completion, "<br>or "))
	end
	cell(
		out,
		"Required items",
		#required > 0 and table.concat(required, "<br>and ") or "No required items."
	)
	if
		variant.rewardMethod == "item_turnin"
		and hasOtherCompletion
		and (variant.experience ~= 0 or variant.gold ~= 0 or variant.item ~= nil)
	then
		cell(out, "Reward condition", "Turn in the required items.")
	end
	if
		variant.experience == 0
		and variant.gold == 0
		and variant.item == nil
		and not hasDialogReward
	then
		cell(out, "Rewards", "No experience, gold, or item reward.")
	else
		cell(
			out,
			"Experience",
			variant.experience == 0 and "No experience reward." or tostring(variant.experience)
		)
		cell(out, "Gold", variant.gold == 0 and "No gold reward." or tostring(variant.gold))
		if variant.item ~= nil or not hasDialogReward then
			cell(
				out,
				"Item reward",
				variant.item
						and (tostring(variant.quantity) .. " x " .. entity("item", variant.item))
					or "No item reward."
			)
		end
	end
	cell(
		out,
		"Faction effects on first completion",
		#factions > 0 and table.concat(factions, "<br>") or "No faction effects recorded."
	)
	if variant.rewardMethod == "item_turnin" then
		cell(
			out,
			"Repeatable",
			'<span data-erenshor-quest-repeatable="'
				.. tostring(variant.repeatable)
				.. '">'
				.. (variant.repeatable and "Yes" or "No")
				.. "</span>"
		)
	end
	local behavior = {}
	if variant.oncePerSpawn then
		table.insert(behavior, effect("once-per-spawn", "Once per spawn."))
	end
	if variant.partialAssigns then
		table.insert(behavior, effect("partial-start", "A partial turn-in starts the quest."))
	end
	if variant.killsHolder then
		table.insert(behavior, effect("recipient-dies", "The recipient dies after turn-in."))
	end
	if variant.dropsInvulnerability then
		table.insert(
			behavior,
			effect("recipient-attackable", "The recipient can be attacked after turn-in.")
		)
	end
	if #behavior > 0 then
		cell(out, "On turn-in", table.concat(behavior, "<br>"))
	end
	if variant.nextQuest then
		cell(
			out,
			"Assigns next quest on first completion",
			effect("assigns-quest", entity("quest", variant.nextQuest))
		)
	end
	if #completes > 0 then
		cell(
			out,
			"Also completes if active",
			effect("completes-quest", table.concat(completes, "<br>"))
		)
	end
	if variant.unlocksItem then
		cell(
			out,
			"Vendor item unlocked",
			effect("unlocks-item", entity("item", variant.unlocksItem))
		)
	end
end

function p.render(args)
	local key, problem = questKey(args or {})
	if key == nil then
		return message(problem)
	end
	local data = mw.loadData("Module:Erenshor/Data/Quests")
	local rows = data[key]
	if rows == nil or rows[1] == nil then
		return message("Missing quest data: " .. key)
	end
	local variants, acquisition, completion = variantsAndRoutes(rows, data)
	if #variants == 0 then
		return message("Missing quest variant data: " .. key)
	end
	local out = { '{| class="wikitable erenshor-quest-data"', "|+ Quest details" }
	cell(
		out,
		"Start",
		#acquisition > 0 and table.concat(acquisition, "<br>or ")
			or "No formal acquisition source recorded."
	)
	cell(
		out,
		"Turn in",
		#completion > 0 and table.concat(completion, "<br>or ") or "No completion source recorded."
	)
	for index, variant in ipairs(variants) do
		variantPanel(out, variant, rows, #variants > 1 and index or nil, data)
	end
	table.insert(out, "|}")
	return table.concat(out, "\n")
end

function p.panel(frame)
	return p.render(Args.parentArgs(frame))
end

return p
