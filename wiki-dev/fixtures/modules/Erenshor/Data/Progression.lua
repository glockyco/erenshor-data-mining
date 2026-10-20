-- A small requirement graph in the format of the generated module, for the
-- testcases and smoke rows of Module:Erenshor/Progression.
local data = {}
local function node(key, kind, name, tier, milestone, page, reward)
	data[key] = {
		{
			type = "node",
			kind = kind,
			label = { key = key, name = name, page = page },
			tier = tier,
			milestone = milestone,
			reward = reward,
		},
	}
end
local function way(key, id, first, sentence, needs)
	table.insert(data[key], { type = "way", way = id, first = first, sentence = sentence })
	for _, need in ipairs(needs) do
		need.type = "need"
		need.way = id
		table.insert(data[key], need)
	end
end

-- Port Azure lies behind a door that the reward of Cat for a Deer opens.
node("zone:PortAzure", "zone", "Port Azure", 6, true, "Port Azure")
node("zone:start", "zone", "Starter Bay", 0, false, "Starter Bay")
node("barrier:fixture-door", "barrier", "A locked door", 5, true)
node("item:lucky_charm", "item", "Lucky Charm", 4, true, "Lucky Charm", "quest:catfordeer")
node("quest:catfordeer", "quest", "Cat for a Deer", 3, true, "Cat for a Deer")
node("quest:fixture-first", "quest", "A first quest", 2, true, "A first quest")
node("character:deer", "character", "A Deer", 0, false, "A Deer")
node("item:catnip", "item", "Catnip", 1, false, "Catnip")
node("mechanism:new_character_start", "mechanism", "New character start", 0, false)
-- A quest to leave undone, and an item that only that quest needs.
node("quest:fixture-undone", "quest", "A quest to leave undone", 8, true, "A quest to leave undone")
node("item:fixture-undone", "item", "An item for that quest", 7, true, "An item for that quest")
node("mechanism:unreachable", "mechanism", "Unreachable source", nil, false)

way("zone:start", "start", true, "Start a new character in {zone:start}.", {
	{ relation = "from", need = "mechanism:new_character_start" },
})
way("mechanism:new_character_start", "initial", true, "Nothing is needed.", {})
way(
	"zone:PortAzure",
	"door",
	true,
	"Travel from {zone:start} to {zone:PortAzure} through {barrier:fixture-door}.",
	{
		{ relation = "barrier", need = "barrier:fixture-door" },
		{ relation = "zone line", need = "zone:start" },
	}
)
for index = 1, 6 do
	local other = "zone:other" .. tostring(index)
	node(other, "zone", "Other bay " .. tostring(index), 0, false)
	way(
		other,
		"start",
		true,
		"Start a new character in {" .. other .. "}.",
		{ { relation = "from", need = "mechanism:new_character_start" } }
	)
	way(
		"zone:PortAzure",
		"entrance" .. tostring(index),
		false,
		"Travel from {" .. other .. "} to {zone:PortAzure}.",
		{ { relation = "zone line", need = other } }
	)
end
way(
	"barrier:fixture-door",
	"key",
	true,
	"Open {barrier:fixture-door} with {item:lucky_charm}, before you finish {quest:fixture-undone}.",
	{
		{ relation = "key", need = "item:lucky_charm" },
		{ relation = "quest not done", need = "quest:fixture-undone" },
	}
)
way("item:lucky_charm", "reward", true, "Finish {quest:catfordeer} for {item:lucky_charm}.", {
	{ relation = "reward", need = "quest:catfordeer" },
})
way(
	"quest:catfordeer",
	"turn in",
	true,
	"Give {item:catnip} to {character:deer} in {zone:start} to finish {quest:catfordeer}, after {quest:fixture-first}.",
	{
		{ relation = "turn in to", need = "character:deer" },
		{ relation = "required item", need = "item:catnip", quantity = 1, slot = "1" },
		{ relation = "quest done", need = "quest:fixture-first" },
	}
)
way(
	"quest:fixture-first",
	"talk",
	true,
	"Talk to {character:deer} in {zone:start} to finish {quest:fixture-first}.",
	{
		{ relation = "talk to", need = "character:deer" },
	}
)
way("character:deer", "home", true, "Find {character:deer} in {zone:start}.", {
	{ relation = "in zone", need = "zone:start" },
})
for index = 1, 6 do
	local wolf = "character:wolf" .. tostring(index)
	node(wolf, "character", "Wolf " .. tostring(index), 0, false)
	way(
		wolf,
		"home",
		true,
		"Find {" .. wolf .. "} in {zone:start}.",
		{ { relation = "in zone", need = "zone:start" } }
	)
	way(
		"item:catnip",
		"drop" .. tostring(index),
		index == 1,
		"Defeat {" .. wolf .. "} in {zone:start} for {item:catnip}.",
		{ { relation = "drops", need = wolf } }
	)
end
way(
	"quest:fixture-undone",
	"turn in",
	true,
	"Give {item:fixture-undone} to {character:deer} in {zone:start} to finish {quest:fixture-undone}.",
	{
		{ relation = "turn in to", need = "character:deer" },
		{ relation = "required item", need = "item:fixture-undone" },
	}
)
way(
	"item:fixture-undone",
	"drop",
	true,
	"Defeat {character:wolf1} in {zone:start} for {item:fixture-undone}.",
	{
		{ relation = "drops", need = "character:wolf1" },
	}
)
way("mechanism:unreachable", "never", false, "Nothing is needed.", {})

-- Four raid planes that all need the Lucky Charm in their planning slot.
for index = 1, 4 do
	local key = "zone:fixture-plane" .. tostring(index)
	node(key, "zone", "Raid plane " .. tostring(index), 5, true)
	way(
		key,
		"planning",
		true,
		"Place {item:lucky_charm} on the planning table to travel to {" .. key .. "}.",
		{
			{
				relation = "planning slot",
				need = "item:lucky_charm",
				slot = "Dedicated" .. tostring(index),
			},
		}
	)
end
node("zone:fixture-rune", "zone", "Ordinary rune destination", 0, true)
way(
	"zone:fixture-rune",
	"rune",
	true,
	"Place {item:lucky_charm} on the planning table to travel to {zone:fixture-rune}.",
	{ { relation = "planning slot", need = "item:lucky_charm", slot = "rune slot" } }
)

-- A chain of fourteen quests behind one area, a chapter long enough to split.
node("zone:fixture-long", "zone", "The long road", 16, true, "The long road")
for index = 1, 14 do
	local key = "quest:fixture-chain" .. tostring(index)
	node(
		key,
		"quest",
		"Chain quest " .. tostring(index),
		index,
		true,
		"Chain quest " .. tostring(index)
	)
	local needs = { { relation = "talk to", need = "character:deer" } }
	local after = ""
	if index > 1 then
		local previous = "quest:fixture-chain" .. tostring(index - 1)
		table.insert(needs, { relation = "quest done", need = previous })
		after = ", after {" .. previous .. "}"
	end
	way(
		key,
		"talk",
		true,
		"Talk to {character:deer} in {zone:start} to finish {" .. key .. "}" .. after .. ".",
		needs
	)
end
way(
	"zone:fixture-long",
	"road",
	true,
	"Travel from {zone:start} to {zone:fixture-long}, after {quest:fixture-chain14}.",
	{
		{ relation = "zone line", need = "zone:start" },
		{ relation = "quest done", need = "quest:fixture-chain14" },
	}
)

-- An isle behind a quest that needs a hatch opened, so the hatch's chapter holds one step.
node("zone:fixture-isle", "zone", "The isle", 4, true, "The isle")
node("quest:fixture-isle", "quest", "Reach the isle", 3, true, "Reach the isle")
node("barrier:fixture-hatch", "barrier", "A hatch", 2, true)
way("barrier:fixture-hatch", "key", true, "Open {barrier:fixture-hatch} with {item:catnip}.", {
	{ relation = "key", need = "item:catnip" },
})
way(
	"quest:fixture-isle",
	"talk",
	true,
	"Talk to {character:deer} in {zone:start} to finish {quest:fixture-isle}, past {barrier:fixture-hatch}.",
	{
		{ relation = "talk to", need = "character:deer" },
		{ relation = "barrier", need = "barrier:fixture-hatch" },
	}
)
way(
	"zone:fixture-isle",
	"boat",
	true,
	"Travel from {zone:start} to {zone:fixture-isle}, after {quest:fixture-isle}.",
	{
		{ relation = "zone line", need = "zone:start" },
		{ relation = "quest done", need = "quest:fixture-isle" },
	}
)

local compact = {
	_meta = {
		defaults = {},
		unmet = { "quest not done" },
		actions = {
			barrier = "get past",
			drops = "defeat",
			["in zone"] = "go to",
			key = "open with",
			["planning slot"] = "place",
			["quest done"] = "finish",
			["required item"] = "give",
			reward = "finish",
			["talk to"] = "talk to",
			["turn in to"] = "give to",
			["zone line"] = "travel from",
		},
		leads = {
			barrier = "Get past {name}",
			character = "Find {name}",
			item = "Get {name}",
			quest = "Finish {name}",
			zone = "Unlock {name}",
		},
	},
}
for index = 1, 4 do
	table.insert(compact._meta.defaults, "zone:fixture-plane" .. tostring(index))
end
for key, rows in pairs(data) do
	local source = rows[1]
	local record = {
		kind = source.kind,
		name = source.label.name,
		page = source.label.page or false,
		tier = source.tier,
		milestone = source.milestone,
		reward = source.reward,
		ways = {},
	}
	local positions, packed = {}, {}
	for _, row in ipairs(rows) do
		if row.type == "way" then
			local position = #record.ways + 1
			positions[row.way] = position
			packed[position] = { mw.text.jsonEncode(row.sentence) }
			if row.first then
				record.first = position
			end
			record.ways[position] = ""
		end
	end
	for _, row in ipairs(rows) do
		if row.type == "need" then
			local values = {}
			for _, field in ipairs({
				"relation",
				"need",
				"quantity",
				"slot",
				"keywords",
				"text",
				"advisory",
				"unconfirmed",
				"required_level",
			}) do
				table.insert(values, row[field] == nil and "null" or mw.text.jsonEncode(row[field]))
			end
			table.insert(packed[positions[row.way]], "[" .. table.concat(values, ",") .. "]")
		end
	end
	for position, parts in ipairs(packed) do
		record.ways[position] = "[" .. table.concat(parts, ",") .. "]"
	end
	if record.page == record.name then
		record.page = nil
	end
	compact[key] = record
end
return compact
