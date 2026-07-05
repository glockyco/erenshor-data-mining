local Args = require("Module:Erenshor/Args")
local Link = require("Module:Erenshor/Link")
local Format = require("Module:Erenshor/Format")
local Cargo = require("Module:Erenshor/Cargo")

local Data = mw.loadData("Module:Erenshor/Data/Characters")

local p = {}

local FIELD_OVERRIDES = {
	ac = "ac",
	agility = "agility",
	charisma = "charisma",
	coordinates = "coordinates",
	droprates = "dropRates",
	elemental = "elemental",
	endurance = "endurance",
	faction = "faction",
	factionchange = "factionChange",
	health = "health",
	image = "image",
	imagecaption = "imageCaption",
	intelligence = "intelligence",
	level = "level",
	levelmodmax = "levelModMax",
	levelmodmin = "levelModMin",
	levelvariancemax = "levelVarianceMax",
	levelvariancemin = "levelVarianceMin",
	magic = "magic",
	mana = "mana",
	name = "name",
	poison = "poison",
	respawn = "respawn",
	spawnchance = "spawnChance",
	spells = "spells",
	strength = "strength",
	title = "name",
	type = "type",
	void = "void",
	wisdom = "wisdom",
	xpmultiplier = "xpMultiplier",
	zones = "zones",
}

local ROOT_PUBLIC_PARAMETERS = {
	"name",
	"title",
	"image",
	"imagecaption",
	"type",
	"faction",
	"factionchange",
	"zones",
	"coordinates",
	"respawn",
	"spawnchance",
	"level",
	"droprates",
	"spells",
	"health",
	"mana",
	"ac",
	"strength",
	"endurance",
	"dexterity",
	"agility",
	"intelligence",
	"wisdom",
	"charisma",
	"magic",
	"poison",
	"elemental",
	"void",
	"levelmodmin",
	"levelmodmax",
	"levelvariancemin",
	"levelvariancemax",
	"xpmultiplier",
}

local function copyTable(value)
	local out = {}
	if value == nil then
		return out
	end
	for key, item in pairs(value) do
		if type(item) == "table" then
			out[key] = copyTable(item)
		else
			out[key] = item
		end
	end
	return out
end

local function templateArgs(frame)
	local out = copyTable(Args.parentArgs(frame))
	if frame ~= nil and frame.args ~= nil then
		for key, value in pairs(frame.args) do
			out[key] = value
		end
	end
	return out
end

local function currentTitleText()
	if mw ~= nil and mw.title ~= nil and mw.title.getCurrentTitle ~= nil then
		return mw.title.getCurrentTitle().text
	end
	return ""
end

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
end

local function ensureImageFile(image, fallbackName)
	local value = image
	if isBlank(value) then
		value = fallbackName
	end
	if isBlank(value) then
		return nil
	end
	value = tostring(value)
	if
		value:match("%.[Pp][Nn][Gg]$")
		or value:match("%.[Jj][Pp][Gg]$")
		or value:match("%.[Jj][Pp][Ee][Gg]$")
	then
		return value
	end
	return value .. ".png"
end

local function explicitStableKey(args)
	return Args.resolve(args, "stablekey", nil)
		or Args.resolve(args, "stableKey", nil)
		or Args.resolve(args, "key", nil)
		or Args.resolve(args, "id", nil)
end

local function resolveStableKey(args)
	local stableKey = explicitStableKey(args)
	if stableKey ~= nil and Data.characters[stableKey] ~= nil then
		return stableKey
	end
	return nil
end

local function applyOverride(character, args, publicName, fieldName)
	if Args.has(args, publicName) then
		character[fieldName] = Args.resolve(args, publicName, character[fieldName])
	end
end

local function applyRootOverrides(character, args)
	for _, publicName in ipairs(ROOT_PUBLIC_PARAMETERS) do
		local fieldName = FIELD_OVERRIDES[publicName]
		if fieldName ~= nil then
			applyOverride(character, args, publicName, fieldName)
		end
	end
end

local function missingCharacter(args, pageTitle)
	return {
		missing = true,
		name = Args.resolve(args, "name", pageTitle) or pageTitle,
		page = pageTitle,
	}
end

function p.resolve(args, pageTitle)
	args = args or {}
	pageTitle = pageTitle or currentTitleText()

	local stableKey = resolveStableKey(args)
	if stableKey == nil then
		return missingCharacter(args, pageTitle)
	end

	local character = copyTable(Data.characters[stableKey])
	character.stableKey = stableKey
	applyRootOverrides(character, args)
	return character
end

local function missingOutput(character)
	return '<span class="erenshor-missing-data">Missing character data: '
		.. Format.escape(character.name)
		.. "</span>[[Category:Pages with missing Erenshor character data]]"
end

local function typeText(characterType)
	if characterType == "NPC" then
		return "[[:Category:Characters|NPC]]"
	end
	if characterType == "Boss" or characterType == "Rare" or characterType == "Enemy" then
		return Format.pageLink("Enemies", characterType)
	end
	return characterType
end

local function categoryForType(characterType)
	if characterType == "Boss" then
		return "[[Category:Bosses]]"
	end
	if characterType == "NPC" then
		return "[[Category:Characters]]"
	end
	if characterType == "[[Simulated Players|Sim]]" then
		return ""
	end
	return "[[Category:Enemies]]"
end

local function mapLink(selector)
	if isBlank(selector) then
		return ""
	end
	local encoded = tostring(selector):gsub(" ", "%%20")
	return "[https://erenshor-maps.wowmuch1.workers.dev/map?sel="
		.. encoded
		.. " View on the interactive map]"
end

local function roundedPositive(value)
	return math.floor(value + 0.5)
end

local function xpMultiplier(c)
	if c.xpMultiplier == nil or c.xpMultiplier == 0 then
		return 1
	end
	return c.xpMultiplier
end

local function experienceRange(c)
	if c.level == nil then
		return nil
	end
	local multiplier = xpMultiplier(c)
	local minimum = roundedPositive(c.level * 4 * multiplier)
	local maximum = roundedPositive(c.level * 9 * multiplier)
	return tostring(minimum) .. "–" .. tostring(maximum)
end

local function linkList(values)
	if type(values) ~= "table" then
		return values
	end
	return Link.join(values, "<br>")
end

local function zoneNames(values)
	if type(values) ~= "table" then
		return values or ""
	end
	local names = {}
	for _, zone in ipairs(values) do
		if type(zone) == "table" and zone.page ~= nil then
			table.insert(names, zone.page)
		elseif type(zone) == "string" then
			table.insert(names, zone)
		end
	end
	return table.concat(names, ",")
end

local function factionChangeList(values)
	if type(values) ~= "table" then
		return values
	end
	local out = {}
	for _, row in ipairs(values) do
		if type(row) == "table" and row.link ~= nil then
			local modifier = tonumber(row.modifier)
			local sign = ""
			if modifier ~= nil and modifier > 0 then
				sign = "+"
			end
			table.insert(out, Link.render(row.link) .. " " .. sign .. tostring(row.modifier))
		end
	end
	return table.concat(out, "<br>")
end

-- Resolve and render one drop's item link from its StableKey. Returns the rendered
-- link plus the item record (so callers can read the page for dedup and the unique
-- flag for the inventory footnote) — nil when the item cannot be resolved.
local function renderDropLink(drop)
	if type(drop) ~= "table" or isBlank(drop.item) then
		return nil, nil
	end
	local item = Link.itemRecord(drop.item)
	if item == nil then
		return nil, nil
	end
	return Link.render({ kind = "item", stablekey = drop.item }), item
end

local function dropRateList(values)
	if type(values) ~= "table" then
		return values
	end
	local out = {}
	local seen = {}
	for _, row in ipairs(values) do
		local rendered, item = renderDropLink(row)
		local probability = tonumber(row.probability)
		if rendered ~= nil and probability ~= nil then
			-- Distinct StableKeys can share a page; collapse identical display rows
			-- (same page, probability, and footnotes) so the infobox lists each once.
			local key = tostring(item.page)
				.. "|"
				.. tostring(row.probability)
				.. "|"
				.. tostring(row.visible == true)
			if not seen[key] then
				seen[key] = true
				local line = rendered .. " (" .. string.format("%.1f", probability) .. "%)"
				if row.visible == true then
					line = line
						.. "<ref>If "
						.. rendered
						.. " is equipped, it is guaranteed to drop.</ref>"
				end
				if item.unique == true then
					line = line
						.. "<ref>If the player is already holding "
						.. rendered
						.. " in their inventory, another will not drop.</ref>"
				end
				table.insert(out, line)
			end
		end
	end
	return table.concat(out, "<br>")
end

-- The guaranteed-pool ("Guaranteed One Of") row is derived from the same drop list:
-- the guaranteed entries, deduplicated by page, shown only when the pool has 2+ so
-- "one of these" is meaningful (a lone guaranteed item simply drops at 100%).
local function guaranteedDropList(values)
	-- An override string belongs to droprates, not the guaranteed pool, which is
	-- derivable only from the structured drop list.
	if type(values) ~= "table" then
		return ""
	end
	local out = {}
	local seen = {}
	for _, row in ipairs(values) do
		if type(row) == "table" and row.guaranteed == true then
			local rendered, item = renderDropLink(row)
			if rendered ~= nil and not seen[tostring(item.page)] then
				seen[tostring(item.page)] = true
				table.insert(out, rendered)
			end
		end
	end
	if #out < 2 then
		return ""
	end
	return table.concat(out, "<br>")
end

local FIELD_ACCESSORS = {
	name = function(c)
		return c.name
	end,
	image = function(c)
		return ensureImageFile(c.image, c.name)
	end,
	imagecaption = function(c)
		return c.imageCaption
	end,
	type = function(c)
		return typeText(c.type)
	end,
	faction = function(c)
		if type(c.faction) == "table" then
			return Link.render(c.faction)
		end
		return c.faction
	end,
	factionchange = function(c)
		return factionChangeList(c.factionChange)
	end,
	map = function(c)
		return mapLink(c.mapSelector)
	end,
	zones = function(c)
		return linkList(c.zones)
	end,
	coordinates = function(c)
		return c.coordinates
	end,
	respawn = function(c)
		return c.respawn
	end,
	spawnchance = function(c)
		return c.spawnChance
	end,
	level = function(c)
		return c.level
	end,
	experience = function(c)
		return experienceRange(c)
	end,
	guaranteeddrops = function(c)
		return guaranteedDropList(c.dropRates)
	end,
	droprates = function(c)
		return dropRateList(c.dropRates)
	end,
	spells = function(c)
		return linkList(c.spells)
	end,
	health = function(c)
		return c.health
	end,
	ac = function(c)
		return c.ac
	end,
	magic = function(c)
		return c.magic
	end,
	poison = function(c)
		return c.poison
	end,
	elemental = function(c)
		return c.elemental
	end,
	void = function(c)
		return c.void
	end,
}

function p.fieldValue(args, pageTitle, key)
	local character = p.resolve(args, pageTitle)
	if character.missing then
		return ""
	end
	local accessor = FIELD_ACCESSORS[key]
	if accessor == nil then
		-- Overridable params without a display accessor still resolve to their generated
		-- data value so override review can detect article params duplicating exported data.
		local overrideField = FIELD_OVERRIDES[key]
		if overrideField ~= nil then
			local raw = character[overrideField]
			if raw == nil then
				return ""
			end
			return tostring(raw)
		end
		error("Unknown Character infobox field: " .. tostring(key))
	end
	local value = accessor(character)
	if value == nil then
		return ""
	end
	return tostring(value)
end

function p.statusText(args, pageTitle)
	local character = p.resolve(args, pageTitle)
	if character.missing then
		return missingOutput(character)
	end
	return categoryForType(character.type)
end

local function cargoFields(character, pageTitle)
	return {
		{ "Page", pageTitle },
		{ "StableKey", character.stableKey },
		{ "Name", character.name },
		{ "Type", character.type },
		{ "Zones", zoneNames(character.zones) },
		{ "Level", character.level },
		{ "BaseArmorPenPercentage", character.baseArmorPenPercentage },
		{ "BaseAttackRollModifier", character.baseAttackRollModifier },
		{ "CannotBeSnared", character.cannotBeSnared },
		{
			"FactionKey",
			type(character.faction) == "table" and (character.faction.stablekey or "") or "",
		},
		{ "HasDrops", character.hasDrops },
		{ "HasSpells", character.hasSpells },
		{ "MapSelector", character.mapSelector },
		{ "CanNeverSeeInvis", character.canNeverSeeInvis },
		{ "DPSDummy", character.dpsDummy },
		{ "IsWyrm", character.isWyrm },
		{ "NoRun", character.noRun },
		{ "NeverAggro", character.neverAggro },
		{ "NoDmgCap", character.noDmgCap },
		{ "CanPhantomStrike", character.canPhantomStrike },
		{ "NoSelfHeal", character.noSelfHeal },
		{ "AggroRegardlessOfLOS", character.aggroRegardlessOfLOS },
		{ "IgnoreLOSForAggro", character.ignoreLOSForAggro },
		{ "SimPlayersIgnoreUntilOrdered", character.simPlayersIgnoreUntilOrdered },
		{ "Enrage", character.enrage },
	}
end

-- One Cargo Drops row per dropped item, keyed by the item StableKey. A manual
-- droprates override replaces dropRates with a display string, which yields no
-- rows (the curator has taken manual control of that relationship).
local function dropCargoRows(character)
	local rows = {}
	if type(character.dropRates) ~= "table" then
		return rows
	end
	for _, drop in ipairs(character.dropRates) do
		if type(drop) == "table" and not isBlank(drop.item) then
			table.insert(rows, {
				{ "CharacterKey", character.stableKey },
				{ "ItemKey", drop.item },
				{ "DropProbability", drop.probability },
				{ "IsGuaranteed", drop.guaranteed == true },
			})
		end
	end
	return rows
end

function p.field(frame)
	return p.fieldValue(templateArgs(frame), currentTitleText(), frame.args[1])
end

function p.status(frame)
	return p.statusText(templateArgs(frame), currentTitleText())
end

function p.cargoArgs(frame)
	local args = templateArgs(frame)
	local pageTitle = currentTitleText()
	local character = p.resolve(args, pageTitle)
	if character.missing then
		return {}
	end
	return Cargo.buildArgs("Characters", cargoFields(character, pageTitle))
end

function p.cargoDropRows(frame)
	local character = p.resolve(templateArgs(frame), currentTitleText())
	local rows = {}
	if not character.missing then
		for _, fields in ipairs(dropCargoRows(character)) do
			table.insert(rows, Cargo.buildArgs("Drops", fields))
		end
	end
	return rows
end

function p.cargoStore(frame)
	local args = templateArgs(frame)
	local pageTitle = currentTitleText()
	local character = p.resolve(args, pageTitle)
	if character.missing then
		return ""
	end
	Cargo.store("Characters", cargoFields(character, pageTitle))
	for _, fields in ipairs(dropCargoRows(character)) do
		Cargo.store("Drops", fields)
	end
	return ""
end

return p
