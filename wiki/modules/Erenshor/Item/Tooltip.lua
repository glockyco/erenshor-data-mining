-- Module:Erenshor/Item/Tooltip
--
-- Presentation layer for item stat tooltips. Faithfully reproduces the live
-- in-game-style tooltip DOM (the live Template:Item/<type> set) with mw.html,
-- reusing the live `item-tooltip-*` CSS classes, but driven by the generated
-- data module instead of per-page flat parameters.
--
-- Faithfulness rules:
--   * Layout, labels, ordering, and which rows appear match the live tooltip
--     exactly (e.g. attributes always shown defaulting to 0, abbreviated labels
--     with no colon, resists as "+N%").
--   * Computed game logic comes from the game, NOT the wiki. The "- 2-Handed"
--     classification and the Base DPS x2 apply only to TwoHandMelee/TwoHandStaff
--     (ItemInfoWindow.cs); bows are not 2-handed. The live wiki keys this off a
--     string label and wrongly includes bows.
--   * Quality is signalled by name color only (live convention): the internal
--     "Godly" key maps to the tier-2 color and never reaches output.

local Format = require("Module:Erenshor/Format")

local Tooltip = {}

local QUALITY_RANK = { ["0"] = 0, Normal = 0, Blessed = 1, Godly = 2 }

-- Tier -> SparkleIcon overlay (Template:SparkleIcon).
local SPARKLE = {
	[0] = { file = "blank.png", size = "0px" },
	[1] = { file = "Blue_Sparkle.gif", size = "80px" },
	[2] = { file = "Purple_Sparkle.gif", size = "80px" },
}

local TYPE_CLASS = {
	Weapon = "item-tooltip-weapon",
	Armor = "item-tooltip-armor",
	Charm = "item-tooltip-charm",
	Consumable = "item-tooltip-consumable",
	General = "item-tooltip-general",
	Aura = "item-tooltip-aura",
	Mold = "item-tooltip-crafting",
	["Skill Book"] = "item-tooltip-book",
	["Spell Scroll"] = "item-tooltip-book",
}

local SLOT_DISPLAY = { PrimaryOrSecondary = "Primary or Secondary" }

-- Authoritative game logic (ItemInfoWindow.cs): only these weapon types are
-- treated as 2-handed for the label and the Base DPS x2.
local TWO_HANDED = { TwoHandMelee = true, TwoHandStaff = true }

-- Class restriction display order (live Item/ClassRestrictions). The data
-- already carries display names (Duelist is stored as Windblade).
local CLASS_ORDER = { "Arcanist", "Druid", "Paladin", "Reaver", "Stormcaller", "Windblade" }

local ATTRIBUTES = {
	{ label = "Str", key = "str" },
	{ label = "End", key = "end" },
	{ label = "Dex", key = "dex" },
	{ label = "Agi", key = "agi" },
	{ label = "Int", key = "int" },
	{ label = "Wis", key = "wis" },
	{ label = "Cha", key = "cha" },
	{ label = "Res", key = "res" },
}

local VITALS = {
	{ label = "Health", key = "hp" },
	{ label = "Mana", key = "mana" },
	{ label = "Armor", key = "ac" },
}

local RESISTS = {
	{ label = "Magic", key = "mr" },
	{ label = "Poison", key = "pr" },
	{ label = "Elemental", key = "er" },
	{ label = "Void", key = "vr" },
}

local function isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
end

local function num(value)
	return tonumber(value) or 0
end

local function tierOf(quality)
	return QUALITY_RANK[quality] or 0
end

local function imageName(item)
	if isBlank(item.image) then
		return nil
	end
	local image = tostring(item.image)
	if not image:match("%.%a+$") then
		image = image .. ".png"
	end
	return image
end

-- Reproduces Template:SparkleIcon for the header icon cell.
local function sparkleIcon(item, tier)
	local image = imageName(item)
	if image == nil then
		return ""
	end
	local sparkle = SPARKLE[tier] or SPARKLE[0]
	return '<div style="position: relative; width: 80px;">'
		.. '<div style="position: absolute; left: 0px; top: 0px; padding: 0;">'
		.. "[[File:"
		.. sparkle.file
		.. "|"
		.. sparkle.size
		.. "]]</div>[[File:"
		.. image
		.. "|80px]]</div>"
end

local function slotDisplay(item)
	if isBlank(item.slot) then
		return nil
	end
	return SLOT_DISPLAY[item.slot] or tostring(item.slot)
end

local function relicSuffix(item)
	if item.relic then
		return " - Relic Item"
	end
	return ""
end

-- Weapon type line: slot (+ " - 2-Handed" for true 2-handed weapons), linked to
-- the Weapons section. No "Slot:" prefix (live convention for weapons).
local function weaponTypeLine(item)
	local slot = slotDisplay(item)
	if slot == nil then
		return nil
	end
	if TWO_HANDED[item.weaponType] then
		slot = slot .. " - 2-Handed"
	end
	return "[[Weapons#" .. slot .. "|" .. slot .. "]]" .. relicSuffix(item)
end

-- Armor type line: "Slot: " + slot, linked to the Armor section.
local function armorTypeLine(item)
	local slot = slotDisplay(item)
	if slot == nil then
		return nil
	end
	return "Slot: [[Armor#" .. slot .. "|" .. slot .. "]]" .. relicSuffix(item)
end

local function header(item, tier, typeLine)
	local node = mw.html.create("table"):addClass("item-tooltip-header")
	local row = node:tag("tr")
	row:tag("td"):addClass("item-tooltip-icon-cell"):wikitext(sparkleIcon(item, tier))
	local nameCell = row:tag("td"):addClass("item-tooltip-name-cell")
	nameCell
		:tag("div")
		:addClass("item-tooltip-name")
		:addClass("item-tooltip-tier-" .. tier)
		:wikitext(Format.escape(item.name or ""))
	if not isBlank(typeLine) then
		nameCell:tag("div"):addClass("item-tooltip-type"):wikitext(typeLine)
	end
	return node
end

local function statRow(parent, label, value)
	local row = parent:tag("div"):addClass("item-tooltip-stats-row")
	row:tag("span"):addClass("item-tooltip-stat-label"):wikitext(label)
	row:tag("span"):addClass("item-tooltip-stat-value"):wikitext(value)
end

-- Item Stats column: 8 attributes always shown (default 0), plus weapon
-- Damage/Delay/Range when present.
local function statsColumn(item, stats, weapon)
	local column = mw.html.create("div"):addClass("item-tooltip-stats-column")
	for _, attr in ipairs(ATTRIBUTES) do
		statRow(column, attr.label, tostring(num(stats[attr.key])))
	end
	if weapon then
		if not isBlank(stats.weaponDamage) then
			statRow(column, "Damage", tostring(stats.weaponDamage))
		end
		if not isBlank(item.weaponDelay) then
			statRow(column, "Delay", tostring(item.weaponDelay) .. " sec")
		end
		local range = nil
		if item.wand and not isBlank(item.wandRange) then
			range = item.wandRange
		elseif item.bow and not isBlank(item.bowRange) then
			range = item.bowRange
		end
		if range ~= nil then
			statRow(column, "Range", tostring(range))
		end
	end
	return column
end

local function simpleColumn(class, rows, stats, valueFn)
	local column = mw.html.create("div"):addClass(class)
	for _, row in ipairs(rows) do
		statRow(column, row.label, valueFn(num(stats[row.key])))
	end
	return column
end

local function twoColumn(item, stats, weapon)
	local wrapper = mw.html.create("div"):addClass("item-tooltip-two-column")
	local left = wrapper:tag("div"):addClass("item-tooltip-left-column")
	left:tag("div"):addClass("item-tooltip-section-header"):wikitext("Item Stats")
	left:node(statsColumn(item, stats, weapon))
	local right = wrapper:tag("div"):addClass("item-tooltip-right-column")
	right:tag("div"):addClass("item-tooltip-section-header"):wikitext("Vitals")
	right:node(simpleColumn("item-tooltip-vitals-column", VITALS, stats, function(value)
		return tostring(value)
	end))
	local resists = right:tag("div"):addClass("item-tooltip-resists-section")
	resists:tag("div"):addClass("item-tooltip-section-header"):wikitext("Resists")
	resists:node(simpleColumn("item-tooltip-resists-column", RESISTS, stats, function(value)
		return "+" .. value .. "%"
	end))
	return wrapper
end

-- Base DPS: deterministic ceil(damage/delay) comparison metric (the real game
-- DPS is player-dependent). x2 only for true 2-handed weapons, per the game.
local function baseDps(item, stats)
	if isBlank(stats.weaponDamage) and isBlank(item.weaponDelay) then
		return nil
	end
	local damage = num(stats.weaponDamage)
	local delay = tonumber(item.weaponDelay) or 1
	if delay == 0 then
		delay = 1
	end
	local dps = math.ceil(damage / delay)
	if TWO_HANDED[item.weaponType] then
		dps = dps * 2
	end
	return dps
end

local function classRestrictions(item)
	if item.classes == nil or #item.classes == 0 then
		return nil
	end
	local present = {}
	for _, name in ipairs(item.classes) do
		present[name] = true
	end
	local node = mw.html.create("div"):addClass("item-tooltip-classes")
	local any = false
	for _, name in ipairs(CLASS_ORDER) do
		if present[name] then
			node:tag("span"):addClass("item-tooltip-class"):wikitext(name)
			any = true
		end
	end
	if not any then
		return nil
	end
	return node
end

local function description(item)
	if isBlank(item.description) then
		return nil
	end
	return mw.html
		.create("div")
		:addClass("item-tooltip-description")
		:wikitext(Format.escape(item.description))
end

-- Assemble one quality tooltip: outer inline-table, header row, body row.
local function tooltipShell(item, tier, typeLine)
	local root = mw.html
		.create("table")
		:addClass("item-tooltip")
		:addClass(TYPE_CLASS[item.type] or "item-tooltip-general")
	local outerCell = root:tag("tr"):tag("td")
	outerCell:node(header(item, tier, typeLine))
	local bodyCell = outerCell:tag("table"):addClass("item-tooltip-body"):tag("tr"):tag("td")
	return root, bodyCell
end

local function gearTooltip(item, stats, weapon, typeLine)
	local root, body = tooltipShell(item, tierOf(stats.quality), typeLine)
	body:node(twoColumn(item, stats, weapon))
	local desc = description(item)
	if desc ~= nil then
		body:node(desc)
	end
	if weapon then
		local dps = baseDps(item, stats)
		if dps ~= nil then
			body:tag("div"):addClass("item-tooltip-dps"):wikitext("Base DPS: " .. dps)
		end
	end
	local classes = classRestrictions(item)
	if classes ~= nil then
		body:node(classes)
	end
	return tostring(root)
end

-- Minimal tooltip for item types whose bodies are not modelled yet (charm,
-- consumable, general, aura, mold, books). Shows the faithful header, lore, and
-- class restrictions; the type-specific body follows in later steps.
local function simpleTooltip(item, stats)
	local typeLine = slotDisplay(item)
	if typeLine ~= nil then
		typeLine = typeLine .. relicSuffix(item)
	elseif item.relic then
		typeLine = "Relic Item"
	end
	local root, body = tooltipShell(item, tierOf(stats.quality), typeLine)
	local desc = description(item)
	if desc ~= nil then
		body:node(desc)
	end
	local classes = classRestrictions(item)
	if classes ~= nil then
		body:node(classes)
	end
	return tostring(root)
end

local function renderQuality(item, stats)
	if item.type == "Weapon" then
		return gearTooltip(item, stats, true, weaponTypeLine(item))
	end
	if item.type == "Armor" then
		return gearTooltip(item, stats, false, armorTypeLine(item))
	end
	return simpleTooltip(item, stats)
end

local function orderedStats(item)
	local stats = {}
	for _, row in ipairs(item.stats or {}) do
		stats[#stats + 1] = row
	end
	table.sort(stats, function(a, b)
		return (QUALITY_RANK[a.quality] or 99) < (QUALITY_RANK[b.quality] or 99)
	end)
	return stats
end

-- Build the full tooltip wikitext for a resolved item. Weapons and armor render
-- one tooltip per quality (distinguished by name color); other items render one.
function Tooltip.render(item)
	local stats = orderedStats(item)
	if #stats <= 1 then
		return renderQuality(item, stats[1] or { quality = "Normal" })
	end
	local parts = {}
	for _, row in ipairs(stats) do
		parts[#parts + 1] = renderQuality(item, row)
	end
	return table.concat(parts, "\n")
end

return Tooltip
