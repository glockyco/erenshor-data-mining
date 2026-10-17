local QuestData = require("Module:Erenshor/QuestData")
local p = {}
local CATEGORY = "[[Category:Pages with missing Erenshor quest data]]"

local function contains(actual, expected, label)
	if string.find(actual, expected, 1, true) == nil then
		error(label .. ": missing " .. expected, 2)
	end
end

local function absent(actual, unexpected, label)
	if string.find(actual, unexpected, 1, true) ~= nil then
		error(label .. ": unexpected " .. unexpected, 2)
	end
end

local function withoutMarkers(text)
	return (string.gsub(text, "UNIQ%-%-[%w%-]+%-QINU", ""))
end

function p.run()
	local kinds = {
		source = true,
		prerequisite = "quest",
		notOwnedItem = "item",
		blockedByQuest = "quest",
		furniture = "item",
		item = "item",
		nextQuest = "quest",
		unlocksItem = "item",
		faction = "faction",
		quest = "quest",
	}
	local seen = {}
	for _, rows in pairs(mw.loadData("Module:Erenshor/Data/Quests")) do
		for _, row in ipairs(rows) do
			for field, kind in pairs(kinds) do
				local reference = row[field]
				if reference ~= nil then
					local expected = field == "source" and row.sourceKind or kind
					if
						type(reference) ~= "table"
						or type(reference.key) ~= "string"
						or string.sub(reference.key, 1, #expected + 1) ~= expected .. ":"
						or type(reference.name) ~= "string"
						or reference.name == ""
						or (reference.page ~= nil and type(reference.page) ~= "string")
					then
						error("Invalid fixture native reference: " .. field)
					end
					seen[field] = true
				end
			end
		end
	end
	for field in pairs(kinds) do
		if not seen[field] then
			error("Missing native reference field coverage: " .. field)
		end
	end
	local eye = QuestData.render({ stablekey = "quest:a skeleton eye for alyssa fearnon" })
	contains(eye, 'data-erenshor-key="character:alyssa fearnon"', "keyword giver identity")
	contains(eye, "favor", "keyword")
	contains(eye, "| 155\n", "experience")
	contains(eye, 'data-erenshor-key="item:belt - 5 - bonestudded belt"', "item reward")
	contains(eye, "1 x ", "quantities")
	contains(eye, "No gold reward.", "explicit zero gold")
	contains(eye, 'data-erenshor-key="faction:fernalla"', "faction effect identity")
	contains(eye, "+1", "positive faction effect")
	contains(eye, "-1", "negative faction effect")
	contains(eye, 'data-erenshor-quest-repeatable="true"', "repeatable turn-in")
	absent(eye, CATEGORY, "successful panel")
	if
		withoutMarkers(eye)
		~= withoutMarkers(QuestData.render({ page = "A Skeleton Eye for Alyssia Fearnon" }))
	then
		error("unambiguous quest page inference differs from explicit stablekey")
	end

	local chain = QuestData.render({ page = "Secure Port Azure" })
	contains(chain, 'data-erenshor-key="quest:inteltokilkay"', "first predecessor")
	contains(chain, 'data-erenshor-key="quest:inteltoripper"', "alternative predecessor")
	contains(chain, "<br>or ", "predecessors are OR alternatives")
	contains(chain, 'data-erenshor-key="character:guard captain azure"', "turn-in recipient")
	contains(chain, 'data-erenshor-quest-method="item_turnin"', "turn-in behavior")
	contains(chain, 'data-erenshor-quest-repeatable="false"', "nonrepeatable turn-in")

	local empty = QuestData.render({ page = "The Tragedy at Goodsoil" })
	contains(empty, "No experience, gold, or item reward.", "explicit absence of rewards")
	absent(empty, 'data-erenshor-quest-route="completion"', "no invented completion")
	absent(empty, "| -", "no reward placeholder")
	absent(empty, "data-erenshor-quest-repeatable", "no invented repeatable turn-in")

	local ambiguous = QuestData.render({ page = "Quest Line Fixture" })
	contains(ambiguous, "quest:shared-line-a, quest:shared-line-b", "shared page identities")
	contains(ambiguous, CATEGORY, "ambiguous page tracked")
	local missing = QuestData.render({ stablekey = "quest:magical_sword" })
	contains(missing, "Missing quest data: quest:magical_sword", "known quest without data")
	contains(missing, CATEGORY, "missing data tracked")
	local unknown = QuestData.render({ page = "No Such Quest Page" })
	contains(unknown, "No quest has the page No Such Quest Page", "unknown page")
	contains(unknown, CATEGORY, "unknown page tracked")

	local variants = QuestData.render({ stablekey = "quest:shared-line-a" })
	absent(variants, CATEGORY, "explicit identity works on shared page")
	local a = string.find(variants, "| Option 1", 1, true)
	local b = string.find(variants, "| Option 2", 1, true)
	if a == nil or b == nil or a >= b then
		error("variant identity and ordering")
	end
	local first = string.sub(variants, a, b - 1)
	local second = string.sub(variants, b)
	contains(first, "3 x ", "first variant required quantity")
	contains(second, "2 x ", "second variant required quantity")
	contains(first, 'data-erenshor-key="quest:catfordeer"', "first variant gate")
	contains(second, 'data-erenshor-key="quest:magical_sword"', "second variant gate")
	absent(
		second,
		'data-erenshor-key="quest:catfordeer"',
		"first gate does not leak to second variant"
	)
	contains(first, 'data-erenshor-quest-effect="once-per-spawn"', "spawn-instance repeat limit")
	contains(first, 'data-erenshor-quest-effect="partial-start"', "partial acquisition")
	contains(first, 'data-erenshor-quest-effect="recipient-dies"', "turn-in holder death")
	contains(first, 'data-erenshor-quest-effect="recipient-attackable"', "holder vulnerability")
	contains(
		first,
		'data-erenshor-quest-effect="completes-quest"',
		"completion consequence is not prerequisite"
	)
	contains(first, "Bellwain's Lost Letters", "pageless native completion condition")
	absent(first, 'data-erenshor-key="quest:bellwainletters2"', "no fabricated quest link")
	absent(first, "[[Bellwain's Lost Letters", "no fabricated quest page")
	contains(first, 'data-erenshor-quest-effect="assigns-quest"', "next quest assignment")
	contains(first, 'data-erenshor-quest-effect="unlocks-item"', "vendor unlock")
	contains(second, "No experience, gold, or item reward.", "variant-specific zero rewards")
	absent(
		second,
		'data-erenshor-quest-effect="recipient-dies"',
		"turn-in behavior does not leak between variants"
	)
	contains(variants, "Event begins", "scripted acquisition note")
	absent(variants, "ShiverEvent.cs", "script filenames stay internal")
	absent(variants, "Variant A", "resource identifiers stay internal")
	absent(variants, "The export", "no implementation disclaimer")
	contains(variants, "Puzzle solved", "scripted completion note")
	contains(variants, 'data-erenshor-key="zone:PortAzure"', "semantic zone source")
	for _, method in ipairs({
		"item_read",
		"zone_entry",
		"scripted",
		"partial_turnin",
		"talk",
		"read",
		"zone",
		"chain",
		"death",
		"shout",
	}) do
		contains(variants, 'data-erenshor-quest-method="' .. method .. '"', method .. " route")
	end
	local following = QuestData.render({ stablekey = "quest:shared-line-b" })
	contains(following, "(option 1)", "source outcome condition stays visible")
	absent(following, "Variant A", "source resource identity stays internal")
	absent(chain, "source variant", "single-outcome predecessor needs no technical qualifier")
	contains(following, "(requires ", "furniture requirement stays visible")
	local furniture = 'data-erenshor-key="item:lucky_charm"'
	local firstFurniture = string.find(following, furniture, 1, true)
	contains(following, furniture, "semantic furniture link")
	if string.find(following, furniture, firstFurniture + 1, true) ~= nil then
		error("identical furniture actions should not repeat for internal room slots")
	end
	absent(following, "L1", "internal room slot stays internal")
	absent(following, "R4", "internal room slot stays internal")
	contains(following, 'data-erenshor-quest-effect="dialog-reward"', "executed dialog item gift")
	contains(following, 'data-erenshor-quest-condition="not-owned"', "dialog inventory gate")
	contains(
		following,
		'data-erenshor-quest-condition="quest-not-completed"',
		"dialog assignment gate"
	)
	contains(
		following,
		'data-erenshor-key="quest:magical_sword"',
		"blocking completed quest identity"
	)
	contains(following, 'data-erenshor-key="quest:catfordeer"', "required completed quest identity")
	absent(
		following,
		"No experience, gold, or item reward.",
		"dialog gift is not erased by empty TradeWindow rewards"
	)
	absent(
		following,
		"data-erenshor-quest-repeatable",
		"dialog gifts do not inherit trade repeatability"
	)

	return "PASS Erenshor QuestData testcases"
end

return p
