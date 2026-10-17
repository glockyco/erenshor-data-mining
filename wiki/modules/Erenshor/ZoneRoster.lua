-- Each row describes an alternative placement condition, never a fixed position.
local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")
local p = {}
local category = "[[Category:Pages with missing Erenshor zone roster data]]"
local tiers = {
	{ "enemy", "Enemies" },
	{ "elite", "Elites" },
	{ "boss", "Bosses" },
	{ "npc", "NPCs" },
	{ "chest", "Chests" },
}

local function message(text)
	return '<span class="erenshor-missing-data">' .. Format.escape(text) .. "</span>" .. category
end

local function percent(value)
	return string.format("%.3g%%", value)
end

local function questReference(reference)
	if
		type(reference) ~= "table"
		or type(reference.key) ~= "string"
		or type(reference.name) ~= "string"
	then
		error("Invalid zone roster quest reference", 2)
	end
	if reference.page then
		return Link.render({ kind = "quest", stablekey = reference.key })
	end
	return Format.escape(reference.name)
end

local function conditions(row)
	local out = {}
	if row.night then
		table.insert(out, "Night only")
	end
	if row.rare then
		table.insert(out, "Rare spawn")
	end
	if row.furniture then
		table.insert(out, "Place " .. Link.render({ kind = "item", stablekey = row.furniture }))
	end
	if row.quest then
		table.insert(out, "Complete " .. questReference(row.quest))
	end
	for _, quest in ipairs(row.stopQuests or {}) do
		table.insert(out, "Stops after " .. questReference(quest))
	end
	if row.triggerItem then
		table.insert(
			out,
			"Requires " .. Link.render({ kind = "item", stablekey = row.triggerItem })
		)
	end
	if row.protector then
		table.insert(
			out,
			"Protector: " .. Link.render({ kind = "character", stablekey = row.protector })
		)
	end
	if row.script then
		table.insert(out, "Event spawn")
	end
	return table.concat(out, "<br>")
end

function p.render(args)
	args = args or {}
	local key = Args.resolve(args, "stablekey", nil)
	if key == nil then
		local page = Args.resolve(args, "page", nil) or mw.title.getCurrentTitle().prefixedText
		local keys = Link.pageKeys("zone", page)
		if #keys ~= 1 then
			return message(
				"Expected one zone on "
					.. page
					.. ". Keys: "
					.. table.concat(keys, ", ")
					.. ". Pass stablekey."
			)
		end
		key = keys[1]
	end
	local rows = mw.loadData("Module:Erenshor/Data/ZoneRosters")[key]
	if rows == nil or rows[1] == nil then
		return message("Missing zone roster data: " .. key)
	end
	local out = {}
	for _, tier in ipairs(tiers) do
		local tableRows = {}
		for _, row in ipairs(rows) do
			if row.tier == tier[1] then
				local level = tostring(row.levelMin)
				if row.levelMax ~= row.levelMin then
					level = level .. " to " .. row.levelMax
				end
				if row.scales then
					level = "Scales with the player's level"
				end
				local chance = "Not specified"
				if row.chanceMin then
					chance = percent(row.chanceMin)
					if row.chanceMax ~= row.chanceMin then
						chance = chance .. " to " .. percent(row.chanceMax)
					end
				end
				table.insert(
					tableRows,
					"|-\n| "
						.. Link.render({ kind = "character", stablekey = row.character })
						.. " || "
						.. level
						.. " || "
						.. chance
						.. " || "
						.. conditions(row)
				)
			end
		end
		if #tableRows > 0 then
			table.insert(
				out,
				'{| class="wikitable sortable"\n|+ '
					.. tier[2]
					.. "\n! Character !! Level !! Spawn chance !! Conditions\n"
					.. table.concat(tableRows, "\n")
					.. "\n|}"
			)
		end
	end
	return table.concat(out, "\n")
end

function p.roster(frame)
	return p.render(Args.parentArgs(frame))
end

return p
