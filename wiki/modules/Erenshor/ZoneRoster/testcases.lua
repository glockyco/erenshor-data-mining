local Roster = require("Module:Erenshor/ZoneRoster")
local p = {}

local function contains(text, expected)
	if not string.find(text, expected, 1, true) then
		error("Missing output: " .. expected)
	end
end

function p.run()
	local output = Roster.render({ stablekey = "zone:PortAzure" })
	contains(output, "|+ Enemies")
	contains(output, "|+ NPCs")
	contains(output, 'data-erenshor-key="character:a_grizzly_bear"')
	contains(output, "9 to 11")
	contains(output, "5% to 10%")
	contains(output, "Night only")
	contains(output, "Rare spawn")
	contains(output, "Place ")
	contains(output, "Complete ")
	contains(output, "Stops after ")
	contains(output, 'data-erenshor-key="quest:magical_sword"')
	contains(output, 'data-erenshor-key="quest:catfordeer"')
	contains(output, "Stops after Capture Leah's Soul")
	if
		string.find(output, 'data-erenshor-key="quest:soulgemleah"', 1, true)
		or string.find(output, "[[Capture Leah's Soul]]", 1, true)
	then
		error("Invented a page link for a resolved pageless quest")
	end
	contains(output, "Event spawn")
	if string.find(output, "FixtureEvent", 1, true) then
		error("Exposed an internal script name")
	end
	contains(Roster.render({ page = "Port Azure" }), "|+ Enemies")
	local missing = Roster.render({ stablekey = "zone:missing" })
	contains(missing, "Missing zone roster data: zone:missing")
	contains(missing, "[[Category:Pages with missing Erenshor zone roster data]]")
	contains(Roster.render({ page = "No Zone Here" }), "Expected one zone")
	return "PASS Erenshor ZoneRoster testcases"
end

return p
