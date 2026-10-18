local data = {}
local function node(key, kind, name, tier, milestone, page)
	data[key] = {
		{
			type = "node",
			kind = kind,
			label = { key = key, name = name, page = page },
			tier = tier,
			milestone = milestone,
		},
	}
end
local function way(key, id, first, needs)
	table.insert(data[key], { type = "way", way = id, first = first })
	for _, need in ipairs(needs) do
		need.type = "need"
		need.way = id
		table.insert(data[key], need)
	end
end

node("zone:PortAzure", "zone", "Port Azure", 4, true, "Port Azure")
node("quest:catfordeer", "quest", "Cat for a Deer", 0, true, "Cat for a Deer")
node("item:lucky_charm", "item", "Lucky Charm", 2, true, "Lucky Charm")
node("barrier:fixture-door", "barrier", "A locked door", 3, true)
node("mechanism:bridge", "mechanism", "A non-milestone bridge", 1, false)
node("mechanism:alternate", "mechanism", "Alternate milestone", 1, true)
node("mechanism:source", "mechanism", "Common ingredient", 0, false)
node("mechanism:unreachable", "mechanism", "Unreachable source", nil, false)
node("character:a_grizzly_bear", "character", "A Grizzly Bear", 3, false, "A Grizzly Bear")
way("quest:catfordeer", "start", true, {})
way("mechanism:bridge", "bridge", true, { { relation = "after", need = "quest:catfordeer" } })
way("item:lucky_charm", "reward", true, { { relation = "reward", need = "mechanism:bridge" } })
way(
	"item:lucky_charm",
	"alternative",
	false,
	{ { relation = "from", need = "mechanism:alternate" } }
)
way("mechanism:alternate", "other", true, {
	{ relation = "defeated", need = "character:a_grizzly_bear", quantity = 1 },
})
way("mechanism:alternate", "without_quantity", false, {
	{ relation = "defeated", need = "character:a_grizzly_bear" },
})
way("barrier:fixture-door", "key", true, { { relation = "key", need = "item:lucky_charm" } })
way(
	"character:a_grizzly_bear",
	"encounter",
	true,
	{ { relation = "release", need = "item:lucky_charm" } }
)
way("zone:PortAzure", "door", true, {
	{ relation = "barrier", need = "barrier:fixture-door" },
	{
		relation = "required item",
		need = "item:lucky_charm",
		quantity = 2,
		slot = "L1",
		keywords = "open",
		advisory = true,
		unconfirmed = true,
		required_level = 8,
	},
	{ relation = "state", text = "Wait for night" },
	{ relation = "material", need = "mechanism:source" },
	{ relation = "from", need = "mechanism:depth1" },
	{ relation = "from", need = "mechanism:unreachable" },
	{ relation = "defeated", need = "character:a_grizzly_bear", quantity = 9 },
})
for index = 1, 7 do
	local key = "mechanism:depth" .. tostring(index)
	node(key, "mechanism", "Depth " .. tostring(index), 0, false)
	way(
		key,
		"deeper",
		true,
		index < 7 and { { relation = "from", need = "mechanism:depth" .. tostring(index + 1) } }
			or {}
	)
end
for index = 1, 6 do
	way(
		"mechanism:source",
		"source" .. tostring(index),
		index == 1,
		{ { relation = "state", text = "Source " .. tostring(index) } }
	)
end
for index = 1, 2 do
	way(
		"zone:PortAzure",
		"entrance" .. tostring(index),
		false,
		{ { relation = "zone line", need = "quest:catfordeer" } }
	)
end
for index = 1, 4 do
	local key = "zone:fixture-plane" .. tostring(index)
	node(key, "zone", "Raid plane " .. tostring(index), 5, true)
	way(key, "planning", true, {
		{
			relation = "planning slot",
			need = "item:lucky_charm",
			slot = "Dedicated" .. tostring(index),
		},
	})
end
node("zone:fixture-rune", "zone", "Ordinary rune destination", 0, true)
way(
	"zone:fixture-rune",
	"rune",
	true,
	{ { relation = "planning slot", need = "item:lucky_charm", slot = "rune slot" } }
)
local compact = { _meta = { defaults = {}, maxDepth = 6 } }
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
		ways = {},
	}
	local positions, needs = {}, {}
	for _, row in ipairs(rows) do
		if row.type == "way" then
			local position = #record.ways + 1
			positions[row.way] = position
			record.ways[position] = "[]"
			needs[position] = {}
			if row.first then
				record.first = position
			end
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
			table.insert(needs[positions[row.way]], "[" .. table.concat(values, ",") .. "]")
		end
	end
	for position, packed in ipairs(needs) do
		record.ways[position] = "[" .. table.concat(packed, ",") .. "]"
	end
	if record.page == record.name then
		record.page = nil
	end
	compact[key] = record
end
return compact
