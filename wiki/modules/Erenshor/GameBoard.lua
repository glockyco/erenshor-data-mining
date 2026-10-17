-- Renders dedicated loot from exact board copies, not character article loot.
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")
local p = {}
local category = "[[Category:Pages with missing Erenshor game board data]]"

local function reference(item)
	if item.page then
		return Link.render({ kind = "item", stablekey = item.key })
	end
	return Format.escape(item.name)
end

local function bosses(data)
	local groups = {}
	local result = {}
	for character, rows in pairs(data) do
		local name = Link.resolve("character", { stablekey = character }).text or character
		for _, row in ipairs(rows) do
			local identity = table.concat({
				character,
				row.copy,
				row.piece.key,
				tostring(row.levelMin),
				tostring(row.levelMax),
				tostring(row.scales),
			}, "\0")
			local boss = groups[identity]
			if boss == nil then
				boss = { character = character, name = name, row = row, drops = {} }
				groups[identity] = boss
				table.insert(result, boss)
			end
			if row.drop then
				table.insert(boss.drops, { item = row.drop, chance = row.chance })
			end
		end
	end
	table.sort(result, function(left, right)
		if left.row.levelMin ~= right.row.levelMin then
			return left.row.levelMin < right.row.levelMin
		end
		if left.name ~= right.name then
			return left.name < right.name
		end
		if left.row.copy ~= right.row.copy then
			return left.row.copy < right.row.copy
		end
		if left.row.piece.key ~= right.row.piece.key then
			return left.row.piece.key < right.row.piece.key
		end
		return left.row.levelMax < right.row.levelMax
	end)
	return result
end

local function lootCell(drops)
	if #drops == 0 then
		return "None"
	end
	table.sort(drops, function(left, right)
		if left.chance ~= right.chance then
			return left.chance > right.chance
		end
		return left.item.name < right.item.name
	end)
	local out = { '<ul class="erenshor-game-board-drops">' }
	for _, drop in ipairs(drops) do
		table.insert(
			out,
			"<li>"
				.. reference(drop.item)
				.. " ("
				.. string.format("%.3g%%", drop.chance)
				.. ")</li>"
		)
	end
	table.insert(out, "</ul>")
	return table.concat(out)
end

function p.render()
	local rows = bosses(mw.loadData("Module:Erenshor/Data/GameBoard"))
	if #rows == 0 then
		return '<span class="erenshor-missing-data">Missing game board data.</span>' .. category
	end
	local out = {
		"At the default loot rate.",
		'{| class="wikitable sortable erenshor-game-board"',
		"|+ Game Board bosses",
		"! Boss !! Level !! Piece !! Drops",
	}
	for _, boss in ipairs(rows) do
		local row = boss.row
		local level = tostring(row.levelMin)
		if row.levelMax ~= row.levelMin then
			level = level .. " to " .. row.levelMax
		end
		if row.scales then
			level = "Scales with the player's level"
		end
		table.insert(out, '|- class="erenshor-game-board-boss"')
		table.insert(
			out,
			"| "
				.. Link.render({ kind = "character", stablekey = boss.character })
				.. ' || data-sort-value="'
				.. row.levelMin
				.. '" | '
				.. level
				.. " || "
				.. reference(row.piece)
				.. " || "
				.. lootCell(boss.drops)
		)
	end
	table.insert(out, "|}")
	return table.concat(out, "\n")
end

function p.board()
	return p.render()
end

return p
