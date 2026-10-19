local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")
local p = {}
local CATEGORY = "[[Category:Pages with missing Erenshor quest list data]]"

local function message(text)
	return '<span class="erenshor-missing-data">' .. mw.text.nowiki(text) .. "</span>" .. CATEGORY
end

local function entity(kind, reference)
	if reference.page then
		return Link.render({ kind = kind, stablekey = reference.key })
	end
	return Format.escape(reference.name)
end

local function item(reference, quantity)
	return tostring(quantity) .. " x " .. entity("item", reference)
end

local function sourceOption(row, data)
	if not row.sourceVariant or not row.source then
		return ""
	end
	local count, index = 0, nil
	for _, variant in ipairs(data[row.source.key] or {}) do
		if variant.type == "variant" then
			count = count + 1
			if variant.variant == row.sourceVariant then
				index = count
			end
		end
	end
	return count > 1 and index and (" (option " .. tostring(index) .. ")") or ""
end

local function route(row, data)
	local methods = {
		dialog = "Talk to ",
		item_read = "Read ",
		zone_entry = "Enter ",
		quest_chain = "Complete ",
		partial_turnin = "Partial item turn-in to ",
		item_turnin = "Item turn-in to ",
		talk = "Talk to ",
		read = "Read ",
		zone = "Enter ",
		chain = "Complete ",
		death = "Defeat ",
		shout = "Shout to ",
	}
	local text = (methods[row.method] or "Event")
		.. (row.source and entity(row.sourceKind, row.source) or "")
		.. sourceOption(row, data)
	if row.keywords then
		text = text .. ' ("' .. Format.escape(row.keywords) .. '")'
	end
	if row.prerequisites then
		local quests = {}
		for _, reference in ipairs(row.prerequisites) do
			table.insert(quests, entity("quest", reference))
		end
		text = text .. ". Requires " .. mw.text.listToText(quests)
	end
	if row.notOwnedItem then
		text = text .. ". Without " .. entity("item", row.notOwnedItem)
	end
	if row.blockedByQuest then
		text = text .. ". Before completing " .. entity("quest", row.blockedByQuest)
	end
	if row.furniture then
		text = text
			.. ". Requires "
			.. entity("item", row.furniture)
			.. " in room "
			.. Format.escape(row.room)
	end
	if row.note then
		text = text .. " (" .. Format.escape(string.gsub(row.note, "^[%w_]+%.cs %- ", "")) .. ")"
	end
	return text
end

local ROUTE_FIELDS = {
	"method",
	"source",
	"sourceKind",
	"sourceVariant",
	"keywords",
	"prerequisites",
	"notOwnedItem",
	"blockedByQuest",
	"furniture",
	"room",
	"note",
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

local function uniqueRoutes(rows, kind, variant)
	local routes = {}
	for _, row in ipairs(rows) do
		if row.type == kind and (row.variant == nil or row.variant == variant) then
			local duplicate = false
			for _, previous in ipairs(routes) do
				local same = true
				for _, field in ipairs(ROUTE_FIELDS) do
					local left, right = identity(row[field]), identity(previous[field])
					if left ~= right then
						same = false
						break
					end
				end
				if same then
					duplicate = true
					break
				end
			end
			if not duplicate then
				table.insert(routes, row)
			end
		end
	end
	return routes
end

local function requirements(rows, variant)
	local grouped, order = {}, {}
	for _, row in ipairs(rows) do
		if row.type == "required" and row.variant == variant then
			local key = row.item.key
			if grouped[key] == nil then
				grouped[key] = { reference = row.item, quantity = 0 }
				table.insert(order, key)
			end
			grouped[key].quantity = grouped[key].quantity + row.quantity
		end
	end
	local text = {}
	for _, key in ipairs(order) do
		table.insert(text, item(grouped[key].reference, grouped[key].quantity))
	end
	return #text > 0 and table.concat(text, "<br>and ") or "None"
end

local function rewards(variant, completion)
	local text = {}
	-- Only the executed item-turn-in outcome receives the generated TradeWindow bundle.
	if completion.method == "item_turnin" and variant.rewardMethod == "item_turnin" then
		if variant.experience ~= 0 then
			table.insert(text, tostring(variant.experience) .. " experience")
		end
		if variant.gold ~= 0 then
			table.insert(text, tostring(variant.gold) .. " gold")
		end
		if variant.item then
			table.insert(text, item(variant.item, variant.quantity))
		end
	elseif completion.item then
		table.insert(text, item(completion.item, completion.quantity))
	end
	return #text > 0 and table.concat(text, ", ") or "No experience, gold, or item reward."
end

function p.render(args, data)
	args = args or {}
	data = data or mw.loadData("Module:Erenshor/Data/Quests")
	local requested = Args.resolve(args, "stablekey", nil)
	if requested and data[requested] == nil then
		return message("Missing quest list data: " .. requested)
	end
	local keys = {}
	for key in pairs(data) do
		if requested == nil or key == requested then
			table.insert(keys, key)
		end
	end
	if #keys == 0 then
		return message("Missing quest list data. Report this at Erenshor Wiki:Game Data.")
	end
	table.sort(keys, function(a, b)
		local left = string.lower(Link.resolve("quest", { stablekey = a }).text)
		local right = string.lower(Link.resolve("quest", { stablekey = b }).text)
		return left < right or (left == right and a < b)
	end)
	local out = {
		"Options are alternatives. Required items within one option are all needed. Rewards belong to the listed completion route.",
		'{| class="wikitable sortable erenshor-quest-list"\n! Quest !! Start !! Required items !! Completion and rewards',
	}
	for _, key in ipairs(keys) do
		local rows, variants = data[key], {}
		for _, row in ipairs(rows) do
			if row.type == "variant" then
				table.insert(variants, row)
			end
		end
		if #variants == 0 then
			return message("Missing quest variants: " .. key)
		end
		for index, variant in ipairs(variants) do
			local starts, outcomes = {}, {}
			for _, row in ipairs(uniqueRoutes(rows, "acquisition", variant.variant)) do
				table.insert(starts, route(row, data))
			end
			for _, row in ipairs(uniqueRoutes(rows, "completion", variant.variant)) do
				local text = route(row, data) .. ": " .. rewards(variant, row)
				if row.method == "item_turnin" then
					text = text .. (variant.repeatable and " (repeatable)" or " (not repeatable)")
				end
				table.insert(outcomes, '<div class="erenshor-quest-outcome">' .. text .. "</div>")
			end
			if #outcomes == 0 then
				table.insert(outcomes, "No experience, gold, or item reward.")
			end
			table.insert(out, "|-")
			table.insert(
				out,
				"| "
					.. Link.render({ kind = "quest", stablekey = key })
					.. (#variants > 1 and ("<br>Option " .. tostring(index)) or "")
			)
			table.insert(
				out,
				"| " .. (#starts > 0 and table.concat(starts, "<br>or ") or "None recorded")
			)
			table.insert(
				out,
				'| class="erenshor-quest-required" | ' .. requirements(rows, variant.variant)
			)
			table.insert(
				out,
				'| class="erenshor-quest-outcomes" | ' .. table.concat(outcomes, "<br>or ")
			)
		end
	end
	table.insert(out, "|}")
	return table.concat(out, "\n")
end

function p.list(frame)
	return p.render(Args.parentArgs(frame))
end

return p
