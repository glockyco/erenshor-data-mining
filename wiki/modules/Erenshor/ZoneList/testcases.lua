local List = require("Module:Erenshor/ZoneList")
local p = {}

local function contains(text, expected)
	if not string.find(text, expected, 1, true) then
		error("Missing output: " .. expected)
	end
end

local function excludes(text, unexpected)
	if string.find(text, unexpected, 1, true) then
		error("Unexpected output: " .. unexpected)
	end
end

function p.run()
	local output = List.render({ ["Port Azure"] = "''Editor note'' [[Port Azure]]" })
	contains(output, 'class="wikitable sortable erenshor-zone-list"')
	contains(output, "5.5 to 6.5")
	contains(output, "No hostiles")
	contains(output, "Not applicable")
	contains(output, "Also scales with the player's level")
	contains(output, 'data-erenshor-zone-conditional="true"')
	contains(output, "Stored return destination")
	contains(output, "Native destination")
	excludes(output, "[[Native destination]]")
	excludes(output, 'data-erenshor-key="zone:pageless-fixture"')
	contains(output, "''Editor note'' [[Port Azure]]")
	excludes(output, "Pages with unknown Erenshor zone notes")
	local unknown = List.render({ ["Misspelled Zone"] = "A note" })
	contains(unknown, "Unknown zone note target: Misspelled Zone")
	contains(unknown, "Use a zone page title as the parameter name.")
	contains(unknown, "[[Category:Pages with unknown Erenshor zone notes]]")
	excludes(List.render({ ["Misspelled Zone"] = " " }), "Unknown zone note target")
	contains(List.render({}, {}), "[[Category:Pages with missing Erenshor zone list data]]")
	contains(List.render({}, { ["zone:PortAzure"] = {} }), "Missing zone summary: zone:PortAzure")
	local data = mw.loadData("Module:Erenshor/Data/Zones")
	local shared = List.render({ ["Overview Shared Zone"] = "Shared note" }, {
		["zone:overview-shared-one"] = data["zone:PortAzure"],
		["zone:overview-shared-two"] = data["zone:PortAzure"],
	})
	local _, count = string.gsub(shared, "Shared note", "")
	if count ~= 2 then
		error("A shared zone page must receive its note on both rows")
	end
	return "PASS Erenshor ZoneList testcases"
end

return p
