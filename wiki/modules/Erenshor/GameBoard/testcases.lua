local Board = require("Module:Erenshor/GameBoard")
local p = {}

local function contains(text, expected)
	if not string.find(text, expected, 1, true) then
		error("Missing output: " .. expected)
	end
end

local function excludes(text, unwanted)
	if string.find(text, unwanted, 1, true) then
		error("Unexpected output: " .. unwanted)
	end
end

function p.run()
	local output = Board.render()
	local rows = {}
	for row in string.gmatch(output, '|%- class="erenshor%-game%-board%-boss"\n([^\n]*)') do
		table.insert(rows, row)
	end
	if #rows ~= 12 then
		error("Expected 12 board bosses, got " .. #rows)
	end
	local function bossRow(key)
		for _, row in ipairs(rows) do
			if string.find(row, 'data-erenshor-key="' .. key .. '"', 1, true) then
				return row
			end
		end
		error("Missing boss " .. key)
	end
	contains(rows[1], 'data-erenshor-key="character:peon"')
	contains(rows[1], "18 to 20")
	contains(rows[1], "33.3%")
	contains(rows[1], 'data-erenshor-page="Peon (Game Piece)"')
	contains(rows[#rows], 'data-erenshor-key="character:monarch of the flame"')

	local candlekeeper = bossRow("character:candlekeeper")
	contains(candlekeeper, 'data-sort-value="35" | 35 ||')
	contains(candlekeeper, 'data-erenshor-key="item:quest - game piece the candlekeeper"')
	contains(candlekeeper, "A Strange Figurine")
	contains(candlekeeper, "(100%)")

	local bowmistress = bossRow("character:bowmistress of sivakaya")
	contains(bowmistress, 'data-erenshor-key="item:quest - game piece the faceless sivakayan"')
	contains(bowmistress, "The Faceless")
	contains(bowmistress, "Skill Book: Trick Shot")

	local reaver = bossRow("character:reaver of sivakaya bkp")
	contains(reaver, "Reaver's Steel")
	contains(reaver, "(6.86%)")
	contains(reaver, "Skill Book: Void Slice")
	local _, drops = string.gsub(reaver, "<li>", "")
	if drops ~= 9 then
		error("Expected the summoned Reaver's nine dedicated drops")
	end
	excludes(reaver, "Ring of the Deceiver")
	excludes(reaver, "Resonating Brace")
	return "PASS Erenshor GameBoard testcases"
end

return p
