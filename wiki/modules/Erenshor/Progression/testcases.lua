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

local function before(actual, first, second)
	local left = string.find(actual, first, 1, true)
	local right = string.find(actual, second, 1, true)
	if not (left and right and left < right) then
		error(first .. " is not before " .. second, 2)
	end
end

local function payloadOf(rendered)
	local encoded = string.match(rendered, "<pre[^>]*>(.-)</pre>")
	return mw.text.jsonDecode(mw.text.unstripNoWiki(encoded))
end

function p.run()
	local explicit = Progression.render({ stablekey = "zone:PortAzure" })
	local inferred = Progression.render({ page = "Port Azure" })
	for _, rendered in ipairs({ explicit, inferred }) do
		-- The door's chapter joins the chapter of the area behind it.
		contains(
			rendered,
			'class="erenshor-progression-chapter-number">1</span> Unlock [[Port Azure]]'
		)
		absent(rendered, 'class="erenshor-progression-chapter-number">2</span>')
		contains(rendered, 'data-progression-key="zone:PortAzure"')
		-- Each step is its first way's sentence, with its nodes linked.
		contains(
			rendered,
			"Give [[Catnip]] to [[A Deer]] in [[Starter Bay]] to finish [[Cat for a Deer]], after [[A first quest]]."
		)
		before(
			rendered,
			'data-progression-key="quest:fixture&#32;&#32;first"',
			'data-progression-key="quest:catfordeer"'
		)
		contains(rendered, "Travel from [[Starter Bay]] to [[Port Azure]] through A locked door.")
		-- The reward of the quest is named in the quest's step, not as a step of its own.
		contains(rendered, 'class="erenshor-progression-yields">You get [[Lucky Charm]].')
		absent(rendered, 'data-progression-key="item:lucky_charm"')
		before(
			rendered,
			'data-progression-key="quest:catfordeer"',
			'data-progression-key="barrier:fixture-door"'
		)
		before(
			rendered,
			'data-progression-key="barrier:fixture-door"',
			'data-progression-key="zone:PortAzure"'
		)
		-- A quest to leave undone is a condition, and the route holds nothing that only it needs.
		contains(rendered, "before you finish [[A quest to leave undone]].")
		absent(rendered, 'data-progression-key="quest:fixture-undone"')
		absent(rendered, "An item for that quest")
		-- One disclosure holds the other ways of a step and where to get what it needs.
		contains(rendered, ">Other ways and sources</span>")
		contains(rendered, "Where to get [[Catnip]]")
		contains(rendered, "Defeat Wolf 4 in [[Starter Bay]] for [[Catnip]].")
		contains(rendered, ">2 more ways</span>")
		before(rendered, "Defeat Wolf 4", ">2 more ways</span>")
		before(rendered, ">2 more ways</span>", "Defeat Wolf 5")
		-- A character whose only way is its zone has no list of its own, and an open area has none either.
		absent(rendered, "Where to find [[A Deer]]")
		absent(rendered, "How to reach")
		contains(
			rendered,
			"These steps are one order of play from a new character's start, not a check of your own character."
		)
		absent(rendered, "tier")
		absent(rendered, CATEGORY)
		contains(rendered, 'class="erenshor-progression-graph"')
		local payload = payloadOf(rendered)
		if
			payload.targets[1] ~= "zone:PortAzure"
			or payload.chapters[1].title ~= "Unlock Port Azure"
		then
			error("Gadget JSON loses its target or its chapters")
		end
		if
			#payload.chapters[1].parts[1].steps ~= 4
			or payload.steps["zone:PortAzure"].deps[1] ~= "barrier:fixture-door"
		then
			error("Gadget JSON loses the steps of a chapter or what a step needs")
		end
		if payload.steps["quest:catfordeer"].folds[1] ~= "item:lucky_charm" then
			error("Gadget JSON loses the reward that a quest's step names")
		end
		if
			not payload.nodes["zone:start"]
			or payload.nodes["item:fixture-undone"]
			or payload.nodes["zone:fixture-plane1"]
		then
			error("Gadget JSON must hold the route and only the route")
		end
		if payload.unmet[1] ~= "quest not done" or payload.actions.drops ~= "defeat" then
			error("Gadget JSON must carry the unmet relations and the actions")
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
	contains(unreachable, "Unreachable source: no way from a new character's start is recorded.")
	-- A step that several goals need, and that nothing serving as many needs, ends a chapter of its own.
	local explorer = Progression.render({ page = "Progression Graph" })
	for index = 1, 4 do
		contains(explorer, 'data-progression-key="zone:fixture-plane' .. tostring(index) .. '"')
	end
	contains(
		explorer,
		'class="erenshor-progression-chapter-number">1</span> Finish [[Cat for a Deer]]'
	)
	contains(explorer, 'class="erenshor-progression-chapter-number">5</span> Unlock Raid plane 4')
	absent(explorer, 'data-progression-key="zone:fixture-rune"')
	-- A chapter of more than twelve steps splits at its quests. A part of one step joins the next.
	local long = Progression.render({ stablekey = "zone:fixture-long" })
	contains(long, 'aria-level="4">Finish [[Chain quest 2]]</div>')
	absent(long, 'aria-level="4">Finish [[Chain quest 1]]</div>')
	absent(long, 'aria-level="4">Unlock [[The long road]]</div>')
	before(
		long,
		'data-progression-key="quest:fixture-chain14"',
		'data-progression-key="zone:fixture-long"'
	)
	contains(long, '<ol class="erenshor-progression-steps" start="3">')
	-- A chapter of one step, here the hatch's, joins the chapter after it.
	local isle = Progression.render({ stablekey = "zone:fixture-isle" })
	contains(isle, 'class="erenshor-progression-chapter-number">1</span> Unlock [[The isle]]')
	absent(isle, 'class="erenshor-progression-chapter-number">2</span>')
	before(
		isle,
		'data-progression-key="barrier:fixture-hatch"',
		'data-progression-key="quest:fixture-isle"'
	)
	return "PASS Erenshor Progression testcases"
end

return p
