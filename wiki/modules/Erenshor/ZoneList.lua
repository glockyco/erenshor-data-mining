local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")
local p = {}
local MISSING = "[[Category:Pages with missing Erenshor zone list data]]"
local NOTES = "[[Category:Pages with unknown Erenshor zone notes]]"

local function message(text, category)
	return '<span class="erenshor-missing-data">' .. mw.text.nowiki(text) .. "</span>" .. category
end

local function range(low, high)
	if low == high then
		return tostring(low)
	end
	return tostring(low) .. " to " .. tostring(high)
end

local function destination(reference)
	if reference.page then
		return Link.render({ kind = "zone", stablekey = reference.key })
	end
	return Format.escape(reference.name)
end

function p.render(args, data)
	args = args or {}
	data = data or mw.loadData("Module:Erenshor/Data/Zones")
	local zones, pages = {}, {}
	for key, rows in pairs(data) do
		local summary
		for _, row in ipairs(rows) do
			if row.type == "summary" then
				summary = row
			end
		end
		if summary == nil then
			return message("Missing zone summary: " .. key, MISSING)
		end
		local identity = Link.resolve("zone", { stablekey = key })
		pages[identity.page] = true
		table.insert(zones, { key = key, rows = rows, summary = summary, identity = identity })
	end
	if #zones == 0 then
		return message("Missing zone list data. Report this at Erenshor Wiki:Game Data.", MISSING)
	end
	table.sort(zones, function(a, b)
		local left, right = string.lower(a.identity.text), string.lower(b.identity.text)
		return left < right or (left == right and a.key < b.key)
	end)
	local errors = {}
	for target, value in pairs(args) do
		if tostring(value):match("%S") and not pages[target] then
			table.insert(errors, tostring(target))
		end
	end
	table.sort(errors)
	local out = {}
	for _, target in ipairs(errors) do
		table.insert(
			out,
			message(
				"Unknown zone note target: "
					.. target
					.. ". Use a zone page title as the parameter name.",
				NOTES
			)
		)
	end
	table.insert(out, "Conditional exits may require unlocks.")
	table.insert(
		out,
		'{| class="wikitable sortable erenshor-zone-list"\n! Zone !! Type !! Hostile levels !! Median level !! Connections !! Notes'
	)
	for _, zone in ipairs(zones) do
		local summary = zone.summary
		local levels, median = "No fixed-level hostiles", "Not applicable"
		if summary.hostileCount == 0 then
			levels = "No hostiles"
		elseif summary.levelMin then
			levels = range(summary.levelMin, summary.levelMax)
			median = range(summary.levelMedianMin, summary.levelMedianMax)
		end
		if summary.scalingCount > 0 then
			levels = levels .. "<br>Also scales with the player's level"
		end
		local connections, seen = {}, {}
		for _, row in ipairs(zone.rows) do
			if row.type == "connection" then
				local identity = row.destination and row.destination.key or row.kind
				local token = identity .. ":" .. tostring(row.conditional)
				if not seen[token] then
					seen[token] = true
					local text = row.kind == "stored_return" and "Stored return destination"
						or destination(row.destination)
					if row.conditional then
						text = text
							.. ' <span data-erenshor-zone-conditional="true">(conditional)</span>'
					end
					table.insert(connections, text)
				end
			end
		end
		table.insert(out, "|-")
		table.insert(out, "| " .. Link.render({ kind = "zone", stablekey = zone.key }))
		table.insert(out, "| " .. Format.escape(summary.zoneType))
		table.insert(out, '| class="erenshor-zone-levels" | ' .. levels)
		table.insert(out, '| class="erenshor-zone-median" | ' .. median)
		table.insert(
			out,
			"| " .. (#connections > 0 and table.concat(connections, "<br>") or "None recorded")
		)
		-- Notes deliberately retain editor wikitext, unlike generated plain-text facts.
		table.insert(out, '| class="erenshor-zone-notes" | ' .. (args[zone.identity.page] or ""))
	end
	table.insert(out, "|}")
	return table.concat(out, "\n")
end

function p.list(frame)
	return p.render(Args.parentArgs(frame))
end

return p
