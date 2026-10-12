local WorldDrops = require("Module:Erenshor/WorldDrops")

local p = {}

local function assertContains(actual, expected, label)
	if string.find(actual, expected, 1, true) == nil then
		error(
			string.format("%s: expected output to contain %s, got %s", label, expected, actual),
			2
		)
	end
end

local function assertBefore(actual, first, second, label)
	local firstAt = string.find(actual, first, 1, true)
	local secondAt = string.find(actual, second, 1, true)
	if firstAt == nil or secondAt == nil or firstAt > secondAt then
		error(string.format("%s: expected %s before %s", label, first, second), 2)
	end
end

function p.run()
	local drops = WorldDrops.render()
	assertContains(drops, "|+ World drops", "caption")
	assertContains(drops, "! Item !! Chance per kill !! Lowest enemy level", "header")
	assertContains(drops, "The chances hold at the default loot rate.", "loot rate note")
	assertContains(
		drops,
		'data-erenshor-key="item:ember_longsword"',
		"item rendered through the link module"
	)
	assertContains(drops, '| 1% || data-sort-value="11" | 11', "gated roll from its lowest level")
	assertContains(drops, '| 0.625% || data-sort-value="1" | Any', "roll of every enemy")
	assertContains(drops, "| 0.00653%", "three significant digits")
	assertBefore(drops, "item:ember_longsword", "item:bear_claw", "likelier roll first")
	assertBefore(drops, "item:bear_claw", "item:healing_draught", "rarest roll last")
	return "PASS Erenshor WorldDrops testcases"
end

return p
