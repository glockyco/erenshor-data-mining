local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")

local p = {}
local CATEGORY = "[[Category:Pages with missing Erenshor progression data]]"
local invocation = 0

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

local function plain(value)
	if type(value) ~= "table" then
		return value
	end
	local copy = {}
	for key, child in pairs(value) do
		copy[key] = plain(child)
	end
	return copy
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
						local needs = {}
						for _, need in ipairs(mw.text.jsonDecode(encoded)) do
							table.insert(needs, {
								relation = need[1],
								need = need[2],
								quantity = need[3],
								slot = need[4],
								keywords = need[5],
								text = need[6],
								advisory = need[7],
								unconfirmed = need[8],
								required_level = need[9],
							})
						end
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
					if need.need then
						visit(need.need)
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

local function needText(need, nodes)
	local defeat = need.relation == "defeated" or need.relation == "defeat"
	local text = Format.escape(need.relation) .. ": "
	if defeat then
		text = need.quantity
				and need.quantity > 1
				and ("Defeat all " .. tostring(need.quantity) .. " ")
			or "Defeat "
	elseif need.quantity then
		text = text .. tostring(need.quantity) .. " x "
	end
	if need.need then
		text = text .. label(nodes[need.need])
	end
	if need.text then
		text = text
			.. (need.need and " (" or "")
			.. Format.escape(need.text)
			.. (need.need and ")" or "")
	end
	if need.slot then
		text = text .. " (slot " .. Format.escape(need.slot) .. ")"
	end
	if need.keywords then
		text = text .. ' (keywords: "' .. Format.escape(need.keywords) .. '")'
	end
	if need.required_level then
		text = text .. " (level " .. tostring(need.required_level) .. ")"
	end
	if need.advisory then
		text = text .. " (advisory)"
	end
	if need.unconfirmed then
		text = text .. " (player access unconfirmed)"
	end
	return text
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
	local function reference(key, suffix)
		return Format.pageLink("#" .. anchors[key], suffix)
	end
	local renderWays
	local function renderNeed(need, depth)
		local text = needText(need, nodes)
		local key = need.need
		if not key then
			return "<li>" .. text .. "</li>"
		end
		if milestones[key] or seen[key] then
			return "<li>" .. text .. " (" .. reference(key, "see above or below") .. ")</li>"
		end
		if depth >= maxDepth then
			return '<li class="erenshor-progression-depth-limit">'
				.. text
				.. " (depth limit reached)</li>"
		end
		seen[key] = true
		return '<li id="' .. anchors[key] .. '">' .. text .. renderWays(key, depth + 1) .. "</li>"
	end
	local function renderWay(way, depth)
		local out = {
			'<li class="erenshor-progression-way">All of' .. (way.first and " (first way)" or ""),
		}
		if #way.needs == 0 then
			table.insert(out, ": no further requirements.")
		else
			table.insert(out, "<ul>")
			for _, need in ipairs(way.needs) do
				table.insert(out, renderNeed(need, depth))
			end
			table.insert(out, "</ul>")
		end
		table.insert(out, "</li>")
		return table.concat(out)
	end
	renderWays = function(key, depth)
		local record = nodes[key]
		if #record.ways == 0 then
			return "<p>No recorded way.</p>"
		end
		local visible, sources, entrances = {}, {}, {}
		for index, way in ipairs(record.ways) do
			if
				record.node.kind == "zone"
				and #way.needs == 1
				and way.needs[1].relation == "zone line"
			then
				table.insert(entrances, way)
			elseif not record.node.milestone and index > 4 then
				table.insert(sources, way)
			else
				table.insert(visible, way)
			end
		end
		local out = { '<div class="erenshor-progression-ways">Any one of<ul>' }
		for _, way in ipairs(visible) do
			table.insert(out, renderWay(way, depth))
		end
		local function group(ways, name)
			if #ways > 0 then
				table.insert(
					out,
					'<li><div class="mw-collapsible mw-collapsed erenshor-progression-sources"><span class="erenshor-progression-source-count">'
						.. tostring(#ways)
						.. " "
						.. name
						.. '</span><div class="mw-collapsible-content"><ul>'
				)
				for _, way in ipairs(ways) do
					table.insert(out, renderWay(way, depth))
				end
				table.insert(out, "</ul></div></div></li>")
			end
		end
		group(sources, "more sources")
		group(entrances, "gate-free entrances")
		table.insert(out, "</ul></div>")
		return table.concat(out)
	end
	local out = {
		'<div class="erenshor-progression">',
		'<p class="erenshor-progression-legend">Tiers are a playthrough order from a new character\'s start, not advice about your character. Ways are alternatives (any one of). Every need of a way is required (all of). The overview follows first ways. Advisory and unconfirmed needs are labeled.</p>',
		'<div class="erenshor-progression-text"><ol class="erenshor-progression-overview">',
	}
	for _, key in ipairs(ordered) do
		seen[key] = true
		local node = nodes[key].node
		local tier = node.tier and "Playthrough tier " .. tostring(node.tier)
			or "No playthrough tier recorded"
		table.insert(
			out,
			'<li id="' .. anchors[key] .. '" data-progression-key="' .. mw.text.encode(key) .. '">'
		)
		table.insert(out, label(nodes[key]) .. " (" .. tier .. ")" .. renderWays(key, 1) .. "</li>")
	end
	table.insert(out, "</ol></div>")
	-- Copy one node at a time, rather than holding a second graph beside loadData.
	local encoded = {}
	for _, key in ipairs(nodeOrder) do
		table.insert(
			encoded,
			mw.text.jsonEncode(key) .. ":" .. mw.text.jsonEncode(plain(data[key]))
		)
	end
	local payload = '{"targets":'
		.. mw.text.jsonEncode(plain(roots))
		.. ',"nodes":{'
		.. table.concat(encoded, ",")
		.. "}}"
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
	table.insert(out, tostring(container))
	table.insert(out, "</div>")
	return table.concat(out, "\n")
end

function p.graph(frame)
	return p.render(Args.parentArgs(frame))
end

return p
