-- Renders the special world drops from Module:Erenshor/Data/WorldDrops, whose
-- opening comment describes its fields. Names and icons come from
-- Module:Erenshor/Link.
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")

local p = {}

local NOTE = "At the default loot rate."

-- Three significant digits show every chance as the game rolls it, from 1%
-- down to 0.002%, such as the 0.625% of a torn treasure map piece.
local function chanceCell(chance)
	return string.format("%.3g", chance) .. "%"
end

local function levelCell(minLevel)
	if minLevel <= 1 then
		return "Any"
	end
	return tostring(minLevel)
end

local function sortedRolls(data)
	local rolls = {}
	for itemKey, rows in pairs(data) do
		local name = Link.resolve("item", { stablekey = itemKey }).text or itemKey
		for _, row in ipairs(rows) do
			table.insert(rolls, { item = itemKey, name = name, row = row })
		end
	end
	table.sort(rolls, function(left, right)
		if left.row.chance ~= right.row.chance then
			return left.row.chance > right.row.chance
		end
		if left.name ~= right.name then
			return left.name < right.name
		end
		return left.row.minLevel < right.row.minLevel
	end)
	return rolls
end

local function dropTable(rolls)
	local out = {
		'{| class="wikitable sortable"',
		"|+ World drops",
		"! Item !! Drop chance !! Lowest enemy level",
	}
	for _, roll in ipairs(rolls) do
		table.insert(out, "|-")
		table.insert(
			out,
			"| "
				.. Link.render({ kind = "item", stablekey = roll.item })
				.. ' || data-sort-value="'
				.. roll.row.chance
				.. '" | '
				.. chanceCell(roll.row.chance)
				.. ' || data-sort-value="'
				.. roll.row.minLevel
				.. '" | '
				.. levelCell(roll.row.minLevel)
		)
	end
	table.insert(out, "|}")
	return Format.escape(NOTE) .. "\n" .. table.concat(out, "\n")
end

function p.render()
	return dropTable(sortedRolls(mw.loadData("Module:Erenshor/Data/WorldDrops")))
end

function p.drops()
	return p.render()
end

return p
