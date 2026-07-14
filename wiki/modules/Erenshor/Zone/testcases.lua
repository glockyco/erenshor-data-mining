local Zone = require("Module:Erenshor/Zone")

local p = {}

local function assertEqual(actual, expected, label)
	if actual ~= expected then
		error(
			string.format("%s: expected %s, got %s", label, tostring(expected), tostring(actual)),
			2
		)
	end
end

local function assertContains(actual, expected, label)
	if string.find(actual, expected, 1, true) == nil then
		error(string.format("%s: expected output to contain %s", label, expected), 2)
	end
end

function p.run()
	local zone = Zone.resolve({ stablekey = "zone:PortAzure" }, "Anything")
	assertEqual(zone.name, "Port Azure", "stable key resolves zone")
	assertEqual(zone.type, "Zone", "zone type resolves")
	assertEqual(zone.map, "zone:PortAzure", "map selector resolves")

	local pageZone = Zone.resolve({}, "Port Azure")
	assertEqual(pageZone.missing, true, "page title does not resolve zone without stable key")

	local override = Zone.resolve(
		{ stablekey = "zone:PortAzure", title = "Manual Zone", connects = "-" },
		"Manual Zone Override"
	)
	assertEqual(override.name, "Manual Zone", "article title override wins")
	assertEqual(override.connects, nil, "dash sentinel blanks supported fields")

	local zoneKey = { stablekey = "zone:PortAzure" }
	assertEqual(Zone.fieldValue(zoneKey, "Port Azure", "name"), "Port Azure", "field name resolves")
	assertEqual(
		Zone.fieldValue(zoneKey, "Port Azure", "maplink"),
		"[https://erenshor.compendiums.org/map?sel=zone%3APortAzure Map]",
		"field map link resolves"
	)
	assertContains(
		Zone.fieldValue(zoneKey, "Port Azure", "connects"),
		"[[Fernalla's Revival Plains]]",
		"field connections resolve"
	)
	assertContains(
		Zone.statusText(zoneKey, "Port Azure"),
		"[[Category:Zones]]",
		"zone category emits"
	)

	local dungeonKey = { stablekey = "zone:ElderstoneMines" }
	assertEqual(
		Zone.fieldValue(dungeonKey, "The Elderstone Mines", "type"),
		"Dungeon",
		"dungeon type emits"
	)
	assertContains(
		Zone.statusText(dungeonKey, "The Elderstone Mines"),
		"[[Category:Dungeons]]",
		"dungeon category emits"
	)

	local directMap = Zone.renderMapLink({ zone = "PortAzure" }, "Anything")
	assertEqual(
		directMap,
		"[https://erenshor.compendiums.org/map?sel=zone%3APortAzure Map]",
		"MapLink zone parameter renders"
	)

	assertEqual(
		Zone.fieldValue({}, "Unknown Prototype", "name"),
		"",
		"missing zone fields are blank"
	)
	local missing = Zone.statusText({}, "Unknown Prototype")
	assertContains(missing, "Missing zone data: Unknown Prototype", "missing zone is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor zone data]]",
		"missing zone is tracked"
	)

	return "PASS Erenshor Zone testcases"
end

return p
