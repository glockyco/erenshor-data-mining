local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")

local p = {}
local CATEGORY = "[[Category:Pages with missing Erenshor progression data]]"
-- A node that is not a milestone shows this many ways before its other sources collapse.
local SOURCE_LIMIT = 4
local invocation = 0

-- Positions of a packed need, as the header of Module:Erenshor/Data/Progression documents.
local RELATION, NEED, QUANTITY, SLOT, KEYWORDS, TEXT, ADVISORY, UNCONFIRMED, LEVEL =
	1, 2, 3, 4, 5, 6, 7, 8, 9

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

local function graph(data)
	local order = {}
	local nodes = setmetatable({}, {
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
			local record = {
				node = {
					kind = source.kind,
					tier = source.tier,
					milestone = source.milestone,
					label = { name = source.name, page = page },
				},
				ways = {},
			}
			for position, packed in ipairs(source.ways) do
				local encoded = packed
				record.ways[position] = setmetatable({ first = position == source.first }, {
					__index = function(way, field)
						if field ~= "needs" then
							return nil
						end
						local needs = mw.text.jsonDecode(encoded)
						way.needs = needs
						return needs
					end,
				})
			end
			cache[key] = record
			table.insert(order, key)
			return record
		end,
	})
	return nodes, order
end

local function overview(nodes, roots)
	local visited, milestones = {}, {}
	local function visit(key)
		if visited[key] then
			return
		end
		visited[key] = true
		local record = nodes[key]
		if record.node.milestone then
			milestones[key] = true
		end
		for _, way in ipairs(record.ways) do
			if way.first then
				for _, need in ipairs(way.needs) do
					if need[NEED] then
						visit(need[NEED])
					end
				end
			end
		end
	end
	for _, key in ipairs(roots) do
		visit(key)
		milestones[key] = true
	end
	local ordered = {}
	for key in pairs(milestones) do
		table.insert(ordered, key)
	end
	table.sort(ordered, function(a, b)
		local left, right = nodes[a].node.tier or math.huge, nodes[b].node.tier or math.huge
		return left < right or (left == right and a < b)
	end)
	return ordered, milestones
end

local function label(record)
	local reference = record.node.label
	local text = Format.escape(reference.name)
	if reference.page then
		text = Format.pageLink(reference.page, text)
	end
	if record.node.kind == "quest_start" then
		text = "Start " .. text
	end
	return text
end

-- Writes the words of a need through emit, one part at a time.
local function emitNeed(emit, need, nodes)
	local relation, key, quantity = need[RELATION], need[NEED], need[QUANTITY]
	if relation == "defeated" or relation == "defeat" then
		emit(
			quantity and quantity > 1 and ("Defeat all " .. tostring(quantity) .. " ") or "Defeat "
		)
	else
		emit(Format.escape(relation))
		emit(": ")
		if quantity then
			emit(tostring(quantity))
			emit(" x ")
		end
	end
	if key then
		emit(label(nodes[key]))
	end
	if need[TEXT] then
		if key then
			emit(" (")
			emit(Format.escape(need[TEXT]))
			emit(")")
		else
			emit(Format.escape(need[TEXT]))
		end
	end
	if need[SLOT] then
		emit(" (slot ")
		emit(Format.escape(need[SLOT]))
		emit(")")
	end
	if need[KEYWORDS] then
		emit(' (keywords: "')
		emit(Format.escape(need[KEYWORDS]))
		emit('")')
	end
	if need[LEVEL] then
		emit(" (level ")
		emit(tostring(need[LEVEL]))
		emit(")")
	end
	if need[ADVISORY] then
		emit(" (advisory)")
	end
	if need[UNCONFIRMED] then
		emit(" (player access unconfirmed)")
	end
end

function p.render(args)
	local data = mw.loadData("Module:Erenshor/Data/Progression")
	local maxDepth = data._meta.maxDepth
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
	local nodes, nodeOrder = graph(data)
	local ordered, milestones = overview(nodes, roots)
	invocation = invocation + 1
	local prefix = "erenshor-progression-" .. tostring(invocation) .. "-"
	local anchorCount = 0
	local anchors = setmetatable({}, {
		__index = function(cache, key)
			anchorCount = anchorCount + 1
			local anchor = prefix .. tostring(anchorCount)
			cache[key] = anchor
			return anchor
		end,
	})
	local seen = {}
	-- The text is written into one buffer, because nested strings for every level
	-- of a raid route cost more memory than the page that they make.
	local out, size = {}, 0
	local function emit(text)
		size = size + 1
		out[size] = text
	end
	local function reference(key, suffix)
		return Format.pageLink("#" .. anchors[key], suffix)
	end
	local renderWays
	local function renderNeed(need, depth)
		local key = need[NEED]
		if not key then
			emit("<li>")
			emitNeed(emit, need, nodes)
			emit("</li>")
		elseif milestones[key] or seen[key] then
			emit("<li>")
			emitNeed(emit, need, nodes)
			emit(" (" .. reference(key, "see above or below") .. ")</li>")
		elseif depth >= maxDepth then
			emit('<li class="erenshor-progression-depth-limit">')
			emitNeed(emit, need, nodes)
			emit(" (depth limit reached)</li>")
		else
			seen[key] = true
			emit('<li id="' .. anchors[key] .. '">')
			emitNeed(emit, need, nodes)
			renderWays(key, depth + 1)
			emit("</li>")
		end
	end
	local function renderWay(way, depth)
		emit('<li class="erenshor-progression-way">All of' .. (way.first and " (first way)" or ""))
		if #way.needs == 0 then
			emit(": no further requirements.")
		else
			emit("<ul>")
			for _, need in ipairs(way.needs) do
				renderNeed(need, depth)
			end
			emit("</ul>")
		end
		emit("</li>")
	end
	local function renderGroup(ways, name, depth)
		if #ways > 0 then
			emit(
				'<li><div class="mw-collapsible mw-collapsed erenshor-progression-sources"><span class="erenshor-progression-source-count">'
					.. tostring(#ways)
					.. " "
					.. name
					.. '</span><div class="mw-collapsible-content"><ul>'
			)
			for _, way in ipairs(ways) do
				renderWay(way, depth)
			end
			emit("</ul></div></div></li>")
		end
	end
	renderWays = function(key, depth)
		local record = nodes[key]
		if #record.ways == 0 then
			emit("<p>No recorded way.</p>")
			return
		end
		local visible, sources, entrances = {}, {}, {}
		for index, way in ipairs(record.ways) do
			if
				record.node.kind == "zone"
				and #way.needs == 1
				and way.needs[1][RELATION] == "zone line"
			then
				table.insert(entrances, way)
			elseif not record.node.milestone and index > SOURCE_LIMIT then
				table.insert(sources, way)
			else
				table.insert(visible, way)
			end
		end
		emit('<div class="erenshor-progression-ways">Any one of<ul>')
		for _, way in ipairs(visible) do
			renderWay(way, depth)
		end
		renderGroup(sources, "more sources", depth)
		renderGroup(entrances, "gate-free entrances", depth)
		emit("</ul></div>")
	end
	-- Top-level parts are separated by newlines.
	emit('<div class="erenshor-progression">')
	emit("\n")
	emit(
		'<p class="erenshor-progression-legend">Tiers are a playthrough order from a new character\'s start, not advice about your character. Ways are alternatives (any one of). Every need of a way is required (all of). The overview follows first ways. Advisory and unconfirmed needs are labeled.</p>'
	)
	emit("\n")
	emit('<div class="erenshor-progression-text"><ol class="erenshor-progression-overview">')
	for _, key in ipairs(ordered) do
		seen[key] = true
		local node = nodes[key].node
		local tier = node.tier and "Playthrough tier " .. tostring(node.tier)
			or "No playthrough tier recorded"
		emit("\n")
		emit(
			'<li id="' .. anchors[key] .. '" data-progression-key="' .. mw.text.encode(key) .. '">'
		)
		emit("\n")
		emit(label(nodes[key]) .. " (" .. tier .. ")")
		renderWays(key, 1)
		emit("</li>")
	end
	emit("\n")
	emit("</ol></div>")
	-- One jsonEncode call reads the loadData records themselves, so the payload holds no copies.
	local touched = {}
	for _, key in ipairs(nodeOrder) do
		touched[key] = data[key]
	end
	local payload = mw.text.jsonEncode({
		targets = roots,
		maxDepth = maxDepth,
		sourceLimit = SOURCE_LIMIT,
		nodes = touched,
	})
	local container = mw.html
		.create("div")
		:addClass("erenshor-progression-graph")
		:attr("data-erenshor-progression", "1")
		:attr("aria-label", "Progression graph")
	container
		:tag("pre")
		:addClass("erenshor-progression-data")
		:css("display", "none")
		:wikitext(mw.getCurrentFrame():extensionTag("nowiki", payload))
	emit("\n")
	emit(tostring(container))
	emit("\n")
	emit("</div>")
	return table.concat(out)
end

function p.graph(frame)
	return p.render(Args.parentArgs(frame))
end

return p
