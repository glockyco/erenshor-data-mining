-- Renders what a vendor sells from Module:Erenshor/Data/VendorStock, whose
-- opening comment describes its fields. Names and icons come from
-- Module:Erenshor/Link.
local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")

local p = {}

local MISSING_CATEGORY = "[[Category:Pages with missing Erenshor vendor stock data]]"

local function message(text)
	return '<span class="erenshor-missing-data">'
		.. Format.escape(text)
		.. "</span>"
		.. MISSING_CATEGORY
end

local function currentPage()
	return mw.title.getCurrentTitle().prefixedText
end

-- The vendor of an explicit stablekey, or the one vendor whose page is the
-- current page. Returns nil and a message when neither names one vendor.
local function vendorKey(args)
	local stableKey = Args.resolve(args, "stablekey", nil)
	if stableKey ~= nil then
		return stableKey
	end
	local page = Args.resolve(args, "page", nil) or currentPage()
	local keys = Link.pageKeys("character", page)
	if #keys == 0 then
		return nil, "No vendor has the page " .. page .. ". Pass stablekey."
	end
	if #keys > 1 then
		return nil,
			"Several characters have the page "
				.. page
				.. ": "
				.. table.concat(keys, ", ")
				.. ". Pass stablekey."
	end
	return keys[1]
end

local function itemCell(row)
	return Link.render({ kind = "item", stablekey = row.item })
end

local function typeCell(row)
	if row.typePage == nil then
		return Format.escape(row.type)
	end
	return Format.pageLink(row.typePage, row.type)
end

local function conditionCell(row)
	local conditions = {}
	for _, quest in ipairs(row.quests or {}) do
		table.insert(conditions, "Complete " .. Link.render({ kind = "quest", stablekey = quest }))
	end
	for _, furniture in ipairs(row.furniture or {}) do
		table.insert(conditions, "Place " .. Link.render({ kind = "item", stablekey = furniture }))
	end
	return table.concat(conditions, "<br>")
end

local function hasConditions(rows)
	for _, row in ipairs(rows) do
		if row.quests ~= nil or row.furniture ~= nil then
			return true
		end
	end
	return false
end

local function stockTable(rows)
	local conditions = hasConditions(rows)
	local header = "! Item name !! Item type !! Price"
	if conditions then
		header = header .. " !! Unlock condition"
	end
	local out = { '{| class="wikitable sortable"', "|+ Store inventory", header }
	for _, row in ipairs(rows) do
		local cells = { "| " .. itemCell(row), typeCell(row), tostring(row.price) }
		if conditions then
			table.insert(cells, conditionCell(row))
		end
		table.insert(out, "|-")
		table.insert(out, table.concat(cells, " || "))
	end
	table.insert(out, "|}")
	return table.concat(out, "\n")
end

function p.render(args)
	args = args or {}
	local stableKey, problem = vendorKey(args)
	if stableKey == nil then
		return message(problem)
	end
	local rows = mw.loadData("Module:Erenshor/Data/VendorStock")[stableKey]
	if rows == nil then
		return message("Missing vendor stock data: " .. stableKey)
	end
	return stockTable(rows)
end

function p.stock(frame)
	return p.render(Args.parentArgs(frame))
end

return p
