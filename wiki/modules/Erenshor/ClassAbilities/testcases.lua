local Abilities = require("Module:Erenshor/ClassAbilities")
local p = {}

local function contains(text, expected)
	if not string.find(text, expected, 1, true) then
		error("Missing output: " .. expected)
	end
end

function p.run()
	local output = Abilities.render({ page = "Druid" })
	contains(output, "Ember")
	contains(output, "Scroll of Ember")
	contains(output, "Sword Mastery")
	contains(output, "Sword Mastery Manual")
	contains(output, " || 4 || ")
	contains(output, 'data-erenshor-key="spell:ember"')
	contains(output, 'data-erenshor-key="item:scroll_of_ember"')
	contains(Abilities.render({ stablekey = "class:paladin" }), " || Any || ")
	local missing = Abilities.render({ stablekey = "class:missing" })
	contains(missing, "[[Category:Pages with missing Erenshor class abilities data]]")
	contains(
		Abilities.render({ page = "No Class Here" }),
		"[[Category:Pages with missing Erenshor class abilities data]]"
	)
	return "PASS Erenshor ClassAbilities testcases"
end

return p
