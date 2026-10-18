local List = require("Module:Erenshor/QuestList")
local p = {}

local function contains(text, expected)
	if not string.find(text, expected, 1, true) then
		error("Missing output: " .. expected)
	end
end

local function excludes(text, unexpected)
	if string.find(text, unexpected, 1, true) then
		error("Unexpected output: " .. unexpected)
	end
end

function p.run()
	local goodsoil = List.render({ stablekey = "quest:goodsoil" })
	contains(goodsoil, 'data-erenshor-key="quest:goodsoil"')
	contains(goodsoil, "No experience, gold, or item reward.")
	excludes(goodsoil, "1000 experience")
	local eye = List.render({ stablekey = "quest:a skeleton eye for alyssa fearnon" })
	contains(eye, "155 experience")
	contains(eye, 'data-erenshor-key="item:belt - 5 - bonestudded belt"')
	contains(eye, "favor")
	local secure = List.render({ stablekey = "quest:findazynthi" })
	contains(secure, 'data-erenshor-key="quest:inteltokilkay"')
	contains(secure, 'data-erenshor-key="quest:inteltoripper"')
	contains(secure, "<br>or ")
	contains(secure, 'data-erenshor-key="character:guard captain azure"')
	local data = mw.loadData("Module:Erenshor/QuestList/Fixture")
	local output = List.render({}, data)
	contains(output, "Option 1")
	contains(output, "Option 2")
	local required = {}
	for cell in string.gmatch(output, 'class="erenshor%-quest%-required" | ([^\n]*)') do
		table.insert(required, cell)
	end
	if #required ~= 2 then
		error("Expected one required-items cell per alternative")
	end
	contains(required[1], "4 x ")
	excludes(required[1], "<br>and ")
	contains(required[2], "2 x ")
	contains(required[2], "<br>and 3 x ")
	excludes(required[1], "6 x ")
	excludes(required[2], "6 x ")
	local outcomes = {}
	for outcome in string.gmatch(output, '<div class="erenshor%-quest%-outcome">(.-)</div>') do
		table.insert(outcomes, outcome)
	end
	if #outcomes ~= 3 then
		error("Expected separate turn-in, dialog gift, and alternative outcomes")
	end
	contains(outcomes[1], "25 experience, 2 gold, 1 x ")
	excludes(outcomes[1], "3 x ")
	contains(outcomes[2], 'Talk to Native speaker ("gift"): 3 x ')
	excludes(outcomes[2], "experience")
	excludes(outcomes[2], "gold")
	contains(outcomes[3], "75 experience, 4 gold, 2 x ")
	contains(output, "Requires Native prerequisite")
	excludes(output, "[[Native prerequisite]]")
	excludes(output, "[[Native speaker]]")
	contains(output, ". Without ")
	contains(output, ". Before completing ")
	contains(List.render({}, {}), "[[Category:Pages with missing Erenshor quest list data]]")
	contains(List.render({ stablekey = "quest:missing" }), "Missing quest list data: quest:missing")
	return "PASS Erenshor QuestList testcases"
end

function p.fixture()
	return List.render({}, mw.loadData("Module:Erenshor/QuestList/Fixture"))
end

return p
