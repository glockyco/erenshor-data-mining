local Progression = require("Module:Erenshor/Progression")
local p = {}
local CATEGORY = "[[Category:Pages with missing Erenshor progression data]]"

local function contains(actual, expected)
	if not string.find(actual, expected, 1, true) then
		error("Missing " .. expected, 2)
	end
end

local function absent(actual, unexpected)
	if string.find(actual, unexpected, 1, true) then
		error("Unexpected " .. unexpected, 2)
	end
end

function p.run()
	local explicit = Progression.render({ stablekey = "zone:PortAzure" })
	local inferred = Progression.render({ page = "Port Azure" })
	for _, rendered in ipairs({ explicit, inferred }) do
		contains(rendered, 'class="erenshor-progression-overview"')
		contains(rendered, 'data-progression-key="zone:PortAzure"')
		contains(rendered, "[[Port Azure]]")
		contains(rendered, "[[Lucky Charm]]")
		contains(rendered, "A locked door")
		contains(rendered, "[[Cat for a Deer]]")
		contains(rendered, "Any one of")
		contains(rendered, "All of (first way)")
		contains(rendered, "no further requirements")
		contains(rendered, "see above or below")
		contains(rendered, "depth limit reached")
		contains(rendered, "No recorded way.")
		contains(rendered, "2 more sources")
		contains(rendered, "2 gate-free entrances")
		contains(rendered, "Wait for night")
		contains(rendered, "2 x [[Lucky Charm]] (slot L1)")
		contains(rendered, 'keywords: "open"')
		contains(rendered, "(advisory)")
		contains(rendered, "(level 8)")
		contains(rendered, "Defeat all 9 [[A Grizzly Bear]]")
		contains(rendered, "Defeat [[A Grizzly Bear]]")
		absent(rendered, "repeat its requirements for each defeat")
		absent(rendered, "times: [[A Grizzly Bear]]")
		absent(rendered, "Defeat all 1 ")
		absent(rendered, "9 x [[A Grizzly Bear]]")
		contains(rendered, "(player access unconfirmed)")
		contains(
			rendered,
			"Tiers are a playthrough order from a new character's start, not advice about your character."
		)
		absent(rendered, CATEGORY)
		-- Alternative milestones belong to the detail, not to the first-way overview.
		absent(rendered, 'data-progression-key="mechanism:alternate"')
		contains(rendered, "Alternate milestone")
		local first = string.find(rendered, 'data-progression-key="quest:catfordeer"', 1, true)
		local key = string.find(rendered, 'data-progression-key="item:lucky_charm"', 1, true)
		local door = string.find(rendered, 'data-progression-key="barrier:fixture-door"', 1, true)
		local target = string.find(rendered, 'data-progression-key="zone:PortAzure"', 1, true)
		if not (first < key and key < door and door < target) then
			error("Overview is not in playthrough tier order")
		end
		-- A non-milestone contributes its first-way milestone dependency.
		absent(rendered, 'data-progression-key="mechanism:bridge"')
		contains(rendered, 'class="erenshor-progression-graph"')
		local encoded = string.match(rendered, "<pre[^>]*>(.-)</pre>")
		local payload = mw.text.jsonDecode(mw.text.unstripNoWiki(encoded))
		if payload.targets[1] ~= "zone:PortAzure" or not payload.nodes["mechanism:depth6"] then
			error("Gadget JSON loses its target or depth-boundary labels")
		end
		if not payload.nodes["mechanism:alternate"] or payload.nodes["zone:fixture-plane1"] then
			error("Gadget JSON must include alternatives and only the target subgraph")
		end
	end
	local ambiguous = Progression.render({ page = "Dire Wolf" })
	contains(ambiguous, "character:dire_wolf_alpha, character:dire_wolf_young")
	contains(ambiguous, "Pass stablekey.")
	contains(ambiguous, CATEGORY)
	local missing = Progression.render({ stablekey = "quest:magical_sword" })
	contains(missing, "Missing progression data: quest:magical_sword")
	contains(missing, CATEGORY)
	local unreachable = Progression.render({ stablekey = "mechanism:unreachable" })
	contains(unreachable, "No playthrough tier recorded")
	contains(unreachable, "No recorded way.")
	local explorer = Progression.render({ page = "Progression Graph" })
	for index = 1, 4 do
		contains(explorer, 'data-progression-key="zone:fixture-plane' .. tostring(index) .. '"')
	end
	absent(explorer, 'data-progression-key="zone:fixture-rune"')
	return "PASS Erenshor Progression testcases"
end

return p
