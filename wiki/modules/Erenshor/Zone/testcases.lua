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
	assertEqual(pageZone.stableKey, "zone:PortAzure", "page title resolves zone")

	local override = Zone.resolve(
		{ zone = "Port Azure", title = "Manual Zone", connects = "-" },
		"Manual Zone Override"
	)
	assertEqual(override.name, "Manual Zone", "article title override wins")
	assertEqual(override.connects, nil, "dash sentinel blanks supported fields")

	local infobox = Zone.renderInfobox({ stablekey = "zone:PortAzure" }, "Port Azure")
	assertContains(infobox, "Port Azure", "infobox contains name")
	assertContains(
		infobox,
		"[https://erenshor-maps.wowmuch1.workers.dev/map?sel=zone%3APortAzure Map]",
		"infobox contains map link"
	)
	assertContains(infobox, "[[Fernalla's Revival Plains]]", "infobox contains connections")
	assertContains(infobox, "[[Category:Zones]]", "zone category emits")

	local dungeon =
		Zone.renderInfobox({ stablekey = "zone:ElderstoneMines" }, "The Elderstone Mines")
	assertContains(dungeon, "Dungeon", "dungeon type emits")
	assertContains(dungeon, "[[Category:Dungeons]]", "dungeon category emits")

	local directMap = Zone.renderMapLink({ zone = "PortAzure" }, "Anything")
	assertEqual(
		directMap,
		"[https://erenshor-maps.wowmuch1.workers.dev/map?sel=zone%3APortAzure Map]",
		"MapLink zone parameter renders"
	)

	local missing = Zone.renderInfobox({}, "Unknown Prototype")
	assertContains(missing, "Missing zone data: Unknown Prototype", "missing zone is visible")
	assertContains(
		missing,
		"[[Category:Pages with missing Erenshor zone data]]",
		"missing zone is tracked"
	)

	return "PASS Erenshor Zone testcases"
end

return p
