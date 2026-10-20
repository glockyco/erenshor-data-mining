local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")

local p = {}
local CATEGORY = "[[Category:Pages with missing Erenshor progression data]]"
-- A list of more ways than this shows its first ways and collapses the rest.
local SOURCE_LIMIT = 4
-- A chapter of more steps than this splits at its quests.
local CHAPTER_LIMIT = 12
-- Steps of these kinds anchor chapters, and so do goals and shared bottlenecks.
local ANCHORS = { zone = true, barrier = true }
-- What a disclosure calls the ways of a need that is no step of its own.
local SOURCES = {
	item = "Where to get",
	character = "Where to find",
	spell = "How to cast",
	quest_start = "Other ways to start",
}
local invocation = 0

-- Positions of a packed need, as the header of Module:Erenshor/Data/Progression documents.
local RELATION, NEED = 1, 2

local function message(text)
	return '<span class="erenshor-missing-data">' .. Format.escape(text) .. "</span>" .. CATEGORY
end

local function targets(args, data)
	local key = Args.resolve(args, "stablekey", nil)
	if key then
		return { key }
	end
	local page = Args.resolve(args, "page", nil) or mw.title.getCurrentTitle().prefixedText
	local keys = {}
	for _, kind in ipairs({ "zone", "quest", "item", "character" }) do
		for _, candidate in ipairs(Link.pageKeys(kind, page)) do
			table.insert(keys, candidate)
		end
	end
	table.sort(keys)
	if #keys > 1 then
		return nil,
			"Several entities have the page "
				.. page
				.. ": "
				.. table.concat(keys, ", ")
				.. ". Pass stablekey."
	end
	if #keys == 1 then
		return keys
	end
	for _, candidate in ipairs(data._meta.defaults) do
		table.insert(keys, candidate)
	end
	return keys
end

-- Records of the data module. A way is decoded when the view first reads it.
local function graph(data)
	return setmetatable({}, {
		__index = function(cache, key)
			local source = data[key]
			if not source then
				error("Missing progression dependency: " .. key)
			end
			local page = source.page
			if page == nil then
				page = source.name
			elseif page == false then
				page = nil
			end
			local record =
				{ key = key, source = source, name = source.name, page = page, ways = {} }
			for position, packed in ipairs(source.ways) do
				record.ways[position] = setmetatable({ packed = packed }, {
					__index = function(way, field)
						if field ~= "sentence" and field ~= "needs" then
							return nil
						end
						local values = mw.text.jsonDecode(packed)
						local needs = {}
						for index = 2, #values do
							needs[index - 1] = values[index]
						end
						way.sentence = values[1]
						way.needs = needs
						return way[field]
					end,
				})
			end
			if source.first then
				record.first = record.ways[source.first]
			end
			cache[key] = record
			return record
		end,
	})
end

local function sortedKeys(set)
	local list = {}
	for key in pairs(set) do
		table.insert(list, key)
	end
	table.sort(list)
	return list
end

local function join(parts)
	if #parts < 3 then
		return table.concat(parts, " and ")
	end
	return table.concat(parts, ", ", 1, #parts - 1) .. " and " .. parts[#parts]
end

-- The steps of the goals' first-way route, what each needs, and the order in
-- which a reader takes them. A step is a milestone or a goal. An item whose
-- first way is only a quest's reward is shown in that quest's step. A need to
-- keep a quest undone is no requirement, so the route never follows it.
local function route(nodes, roots, unmet)
	local closure, active, isRoot = {}, {}, {}
	local function visit(key)
		if closure[key] then
			return
		end
		if active[key] then
			error("Progression first ways cycle at " .. key)
		end
		active[key] = true
		local way = nodes[key].first
		if way then
			for _, need in ipairs(way.needs) do
				if need[NEED] and not unmet[need[RELATION]] then
					visit(need[NEED])
				end
			end
		end
		active[key] = nil
		closure[key] = true
	end
	for _, key in ipairs(roots) do
		isRoot[key] = true
		visit(key)
	end
	local isStep, unit = {}, {}
	for key in pairs(closure) do
		if nodes[key].source.milestone or isRoot[key] then
			isStep[key] = true
		end
	end
	local folds = {}
	for _, key in ipairs(sortedKeys(isStep)) do
		local reward = nodes[key].source.reward
		if reward and isStep[reward] and not isRoot[key] then
			unit[key] = reward
			folds[reward] = folds[reward] or {}
			table.insert(folds[reward], key)
		else
			unit[key] = key
		end
	end
	-- The steps that a node's first way reaches through nodes that are no steps.
	local reached = {}
	local function nearest(key)
		local found = reached[key]
		if found then
			return found
		end
		found = {}
		local way = nodes[key].first
		if way then
			for _, need in ipairs(way.needs) do
				local target = need[NEED]
				if target and not unmet[need[RELATION]] then
					if isStep[target] then
						found[unit[target]] = true
					else
						for other in pairs(nearest(target)) do
							found[other] = true
						end
					end
				end
			end
		end
		reached[key] = found
		return found
	end
	local depSets = {}
	for key in pairs(isStep) do
		local owner = unit[key]
		depSets[owner] = depSets[owner] or {}
		for other in pairs(nearest(key)) do
			depSets[owner][other] = true
		end
	end
	local function tier(key)
		return nodes[key].source.tier or math.huge
	end
	-- The deepest requirement comes first, so a chain ends before the next step's materials begin.
	local function deepestFirst(left, right)
		local a, b = tier(left), tier(right)
		if a ~= b then
			return a > b
		end
		return left < right
	end
	local deps, users = {}, {}
	for owner, set in pairs(depSets) do
		set[owner] = nil
		local list = sortedKeys(set)
		table.sort(list, deepestFirst)
		deps[owner] = list
		for _, other in ipairs(list) do
			users[other] = users[other] or {}
			table.insert(users[other], owner)
		end
	end
	local walk, walked = {}, {}
	local function walkFrom(key)
		if walked[key] then
			return
		end
		walked[key] = true
		for _, other in ipairs(deps[key]) do
			walkFrom(other)
		end
		table.insert(walk, key)
	end
	for _, key in ipairs(roots) do
		walkFrom(key)
	end
	-- How many goals need each step.
	local goals = {}
	for _, root in ipairs(roots) do
		local seen = {}
		local function mark(key)
			if seen[key] then
				return
			end
			seen[key] = true
			goals[key] = (goals[key] or 0) + 1
			for _, other in ipairs(deps[key]) do
				mark(other)
			end
		end
		mark(root)
	end
	return {
		closure = closure,
		isRoot = isRoot,
		unit = unit,
		folds = folds,
		deps = deps,
		users = users,
		walk = walk,
		goals = goals,
	}
end

-- The steps of `pool` that an anchor needs and no earlier group took, in walk order.
local function take(steps, deps, anchor, pool, taken)
	local members, stack = {}, { anchor }
	while #stack > 0 do
		local key = table.remove(stack)
		if not members[key] and not taken[key] and pool[key] then
			members[key] = true
			for _, other in ipairs(deps[key]) do
				table.insert(stack, other)
			end
		end
	end
	local list = {}
	for _, key in ipairs(steps) do
		if members[key] then
			table.insert(list, key)
			taken[key] = true
		end
	end
	return list
end

-- Chapters end at areas, gates, goals, and the steps that several goals need
-- when everything that needs them serves fewer goals. A gate's chapter joins
-- the chapter of the area behind it, and a long chapter splits at its quests.
local function chapters(nodes, plan)
	local everything = {}
	for _, key in ipairs(plan.walk) do
		everything[key] = true
	end
	local function shared(key)
		local count = plan.goals[key] or 0
		if count < 2 then
			return false
		end
		for _, user in ipairs(plan.users[key] or {}) do
			if (plan.goals[user] or 0) >= count then
				return false
			end
		end
		return true
	end
	local found, taken = {}, {}
	for _, key in ipairs(plan.walk) do
		if ANCHORS[nodes[key].source.kind] or plan.isRoot[key] or shared(key) then
			local steps = take(plan.walk, plan.deps, key, everything, taken)
			if #steps > 0 then
				table.insert(found, { anchor = key, steps = steps })
			end
		end
	end
	local merged = {}
	for _, chapter in ipairs(found) do
		local last = merged[#merged]
		local opens = false
		if
			last
			and nodes[last.anchor].source.kind == "barrier"
			and nodes[chapter.anchor].source.kind == "zone"
		then
			local way = nodes[chapter.anchor].first
			for _, need in ipairs(way and way.needs or {}) do
				if need[NEED] == last.anchor then
					opens = true
				end
			end
		end
		if opens then
			for _, key in ipairs(chapter.steps) do
				table.insert(last.steps, key)
			end
			last.anchor = chapter.anchor
		else
			table.insert(merged, chapter)
		end
	end
	-- A chapter of one step joins the chapter after it, unless the step is a goal.
	local joined, carry = {}, {}
	for index, chapter in ipairs(merged) do
		if #chapter.steps == 1 and not plan.isRoot[chapter.anchor] and index < #merged then
			table.insert(carry, chapter.steps[1])
		else
			for position, key in ipairs(carry) do
				table.insert(chapter.steps, position, key)
			end
			carry = {}
			table.insert(joined, chapter)
		end
	end
	merged = joined
	for _, chapter in ipairs(merged) do
		chapter.parts = { { anchor = chapter.anchor, steps = chapter.steps } }
		if #chapter.steps > CHAPTER_LIMIT then
			local pool, partTaken, parts, carry = {}, {}, {}, {}
			for _, key in ipairs(chapter.steps) do
				pool[key] = true
			end
			for _, key in ipairs(chapter.steps) do
				if key == chapter.anchor or nodes[key].source.kind == "quest" then
					local steps = take(chapter.steps, plan.deps, key, pool, partTaken)
					for _, other in ipairs(steps) do
						table.insert(carry, other)
					end
					-- A part of one step joins the next part.
					if #carry > 1 or key == chapter.anchor then
						table.insert(parts, { anchor = key, steps = carry })
						carry = {}
					end
				end
			end
			-- A last part of one step joins the part before it.
			local last = parts[#parts]
			if #parts > 1 and #last.steps == 1 then
				table.insert(parts[#parts - 1].steps, last.steps[1])
				parts[#parts] = nil
			end
			chapter.parts = parts
		end
	end
	return merged
end

function p.render(args)
	local data = mw.loadData("Module:Erenshor/Data/Progression")
	local roots, problem = targets(args or {}, data)
	if not roots then
		return message(problem)
	end
	if #roots == 0 then
		return message("No raid-plane progression data is available.")
	end
	for _, key in ipairs(roots) do
		if not data[key] then
			return message("Missing progression data: " .. key)
		end
	end
	local unmet = {}
	for _, relation in ipairs(data._meta.unmet) do
		unmet[relation] = true
	end
	local nodes = graph(data)
	local plan = route(nodes, roots, unmet)
	local found = chapters(nodes, plan)
	invocation = invocation + 1
	local prefix = "erenshor-progression-" .. tostring(invocation) .. "-"

	-- The text is written into one buffer, because nested strings for every
	-- step of a raid route cost more memory than the page that they make.
	local out, size = {}, 0
	local function emit(text)
		size = size + 1
		out[size] = text
	end
	local function label(key)
		local record = nodes[key]
		local text = Format.escape(record.name)
		return record.page and Format.pageLink(record.page, text) or text
	end
	-- A sentence names nodes as {stable key}, and each becomes its linked label.
	local function sentence(text)
		local parts, count, position = {}, 0, 1
		for start, key, finish in string.gmatch(text, "(){([^{}]+)}()") do
			parts[count + 1] = Format.escape(string.sub(text, position, start - 1))
			parts[count + 2] = label(key)
			count = count + 2
			position = finish
		end
		parts[count + 1] = Format.escape(string.sub(text, position))
		return table.concat(parts)
	end
	local function lead(key, linked)
		local pattern = data._meta.leads[nodes[key].source.kind] or "{name}"
		local name = linked and label(key) or Format.escape(nodes[key].name)
		return (string.gsub(pattern, "{name}", function()
			return name
		end))
	end
	-- The sentences of a node's ways, each once, without the ones in `shown`.
	local function sentences(key, shown)
		local list = {}
		for _, way in ipairs(nodes[key].ways) do
			local text = sentence(way.sentence)
			if not shown[text] then
				shown[text] = true
				table.insert(list, text)
			end
		end
		return list
	end
	local function emitWays(title, list)
		if #list == 0 then
			return
		end
		emit('<div class="erenshor-progression-more-title">' .. title .. "</div><ul>")
		for index, text in ipairs(list) do
			if index == SOURCE_LIMIT + 1 then
				local rest = #list - SOURCE_LIMIT
				emit(
					'<li class="erenshor-progression-rest"><div class="mw-collapsible mw-collapsed">'
						.. '<span class="mw-collapsible-toggle erenshor-progression-toggle">'
						.. tostring(rest)
						.. (rest == 1 and " more way" or " more ways")
						.. '</span><div class="mw-collapsible-content"><ul>'
				)
			end
			emit("<li>" .. text .. "</li>")
		end
		if #list > SOURCE_LIMIT then
			emit("</ul></div></div></li>")
		end
		emit("</ul>")
	end
	-- Whether a node's ways say more than the step's sentence already does. A
	-- step names a character's zone and the start of its quest. An area that is
	-- no step is open, so how to travel there is left to its page.
	local function worthListing(key)
		local record = nodes[key]
		local kind = record.source.kind
		if #record.ways == 0 or kind == "zone" then
			return false
		end
		if kind == "quest_start" then
			return #record.ways > 1
		end
		if kind == "character" and #record.ways == 1 then
			local needs = record.ways[1].needs
			return not (#needs == 1 and needs[1][RELATION] == "in zone")
		end
		return true
	end
	-- Other ways of a step and of what it yields, and where to get what it
	-- needs, behind one disclosure.
	local function emitMore(key, main)
		local held = {}
		table.insert(
			held,
			{ title = "Other ways", list = sentences(key, main and { [main] = true } or {}) }
		)
		for _, item in ipairs(plan.folds[key] or {}) do
			local shown = {}
			local first = nodes[item].first
			if first then
				shown[sentence(first.sentence)] = true
			end
			table.insert(
				held,
				{ title = "Other ways to get " .. label(item), list = sentences(item, shown) }
			)
		end
		local named = {}
		for _, owner in ipairs({ key, unpack(plan.folds[key] or {}) }) do
			local way = nodes[owner].first
			for _, need in ipairs(way and way.needs or {}) do
				local target = need[NEED]
				if
					target
					and not named[target]
					and not unmet[need[RELATION]]
					and not plan.unit[target]
					and worthListing(target)
				then
					named[target] = true
					local kind = nodes[target].source.kind
					local subject = kind == "quest_start"
							and string.sub(target, #"quest_start:" + 1)
						or target
					local title = (SOURCES[kind] or "How to get") .. " " .. label(subject)
					table.insert(held, { title = title, list = sentences(target, {}) })
				end
			end
		end
		local any = false
		for _, section in ipairs(held) do
			any = any or #section.list > 0
		end
		if not any then
			return
		end
		emit(
			'<div class="mw-collapsible mw-collapsed erenshor-progression-more">'
				.. '<span class="mw-collapsible-toggle erenshor-progression-toggle">Other ways and sources</span>'
				.. '<div class="mw-collapsible-content">'
		)
		for _, section in ipairs(held) do
			emitWays(section.title, section.list)
		end
		emit("</div></div>")
	end
	local number = 0
	local function emitStep(key)
		number = number + 1
		local record = nodes[key]
		local main = record.first and sentence(record.first.sentence)
		emit(
			'<li class="erenshor-progression-step" id="'
				.. prefix
				.. "s"
				.. tostring(number)
				.. '" data-progression-key="'
				.. mw.text.encode(key)
				.. '"><span class="erenshor-progression-sentence">'
				.. (main or (label(key) .. ": no way from a new character's start is recorded."))
				.. "</span>"
		)
		local yields = {}
		for _, item in ipairs(plan.folds[key] or {}) do
			table.insert(yields, label(item))
		end
		if #yields > 0 then
			emit(
				' <span class="erenshor-progression-yields">You get ' .. join(yields) .. ".</span>"
			)
		end
		emitMore(key, main)
		emit("</li>")
	end

	emit('<div class="erenshor-progression">')
	emit("\n")
	emit(
		'<p class="erenshor-progression-legend">These steps are one order of play from a new character\'s start, not a check of your own character. Each step names one way. Other ways, and where to find what a step needs, are under the step.</p>'
	)
	-- The map of the gadget comes before the route, and the text works without it.
	local payloadChapters = {}
	for index, chapter in ipairs(found) do
		local parts = {}
		for position, part in ipairs(chapter.parts) do
			parts[position] = { title = lead(part.anchor, false), steps = part.steps }
		end
		payloadChapters[index] = { title = lead(chapter.anchor, false), parts = parts }
	end
	local payloadSteps = {}
	for _, key in ipairs(plan.walk) do
		payloadSteps[key] = { deps = plan.deps[key], folds = plan.folds[key] }
	end
	local payloadNodes = {}
	for key in pairs(plan.closure) do
		local source = nodes[key].source
		payloadNodes[key] = {
			kind = source.kind,
			name = source.name,
			page = source.page,
			way = nodes[key].first and nodes[key].first.packed,
		}
	end
	local payload = mw.text.jsonEncode({
		targets = roots,
		unmet = data._meta.unmet,
		actions = data._meta.actions,
		chapters = payloadChapters,
		steps = payloadSteps,
		nodes = payloadNodes,
	})
	local container = mw.html
		.create("div")
		:addClass("erenshor-progression-graph")
		:attr("data-erenshor-progression", "1")
		:attr("aria-label", "Chapter map")
	container
		:tag("pre")
		:addClass("erenshor-progression-data")
		:css("display", "none")
		:wikitext(mw.getCurrentFrame():extensionTag("nowiki", payload))
	emit("\n")
	emit(tostring(container))
	emit("\n")
	emit('<div class="erenshor-progression-route">')
	for index, chapter in ipairs(found) do
		emit("\n")
		emit(
			'<div class="erenshor-progression-chapter" id="'
				.. prefix
				.. "c"
				.. tostring(index)
				.. '" data-progression-chapter="'
				.. tostring(index)
				.. '"><div class="erenshor-progression-chapter-title" role="heading" aria-level="3">'
				.. '<span class="erenshor-progression-chapter-number">'
				.. tostring(index)
				.. "</span> "
				.. lead(chapter.anchor, true)
				.. "</div>"
		)
		for _, part in ipairs(chapter.parts) do
			if #chapter.parts > 1 then
				emit(
					'<div class="erenshor-progression-part-title" role="heading" aria-level="4">'
						.. lead(part.anchor, true)
						.. "</div>"
				)
			end
			emit('<ol class="erenshor-progression-steps" start="' .. tostring(number + 1) .. '">')
			for _, key in ipairs(part.steps) do
				emitStep(key)
			end
			emit("</ol>")
		end
		emit("</div>")
	end
	emit("\n")
	emit("</div></div>")
	return table.concat(out)
end

function p.graph(frame)
	return p.render(Args.parentArgs(frame))
end

return p
