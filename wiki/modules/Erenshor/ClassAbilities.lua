-- Renders the item-learning relationships documented in Data/ClassAbilities.
local Args = require("Module:Erenshor/Args")
local Format = require("Module:Erenshor/Format")
local Link = require("Module:Erenshor/Link")
local p = {}
local category = "[[Category:Pages with missing Erenshor class abilities data]]"

local function message(text)
	return '<span class="erenshor-missing-data">' .. Format.escape(text) .. "</span>" .. category
end

function p.render(args)
	args = args or {}
	local key = Args.resolve(args, "stablekey", nil)
	if key == nil then
		local page = Args.resolve(args, "page", nil) or mw.title.getCurrentTitle().prefixedText
		local keys = Link.pageKeys("class", page)
		if #keys ~= 1 then
			return message(
				"Expected one class on "
					.. page
					.. ". Keys: "
					.. table.concat(keys, ", ")
					.. ". Pass stablekey."
			)
		end
		key = keys[1]
	end
	local rows = mw.loadData("Module:Erenshor/Data/ClassAbilities")[key]
	if rows == nil or rows[1] == nil then
		return message("Missing class abilities data: " .. key)
	end
	local out = {
		'{| class="wikitable sortable"',
		"|+ Abilities and spells",
		"! Ability !! Required level !! Learned from",
	}
	for _, row in ipairs(rows) do
		local items = {}
		for _, item in ipairs(row.items) do
			table.insert(items, Link.render({ kind = "item", stablekey = item }))
		end
		table.insert(out, "|-")
		table.insert(
			out,
			"| "
				.. Link.render({ kind = "ability", stablekey = row.ability })
				.. " || "
				.. (row.level < 1 and "Any" or tostring(row.level))
				.. " || "
				.. table.concat(items, "<br>")
		)
	end
	table.insert(out, "|}")
	return table.concat(out, "\n")
end

function p.abilities(frame)
	return p.render(Args.parentArgs(frame))
end

return p
