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
local Common = require("Module:Erenshor/Ability/Common")

-- Effect spells and taught skills are joined by stable key (best-practice
-- mw.loadData: parsed once per page, cached, read-only static data).
local SpellData = mw.loadData("Module:Erenshor/Data/Spells")
local SkillData = mw.loadData("Module:Erenshor/Data/Skills")

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

local isBlank = Common.isBlank
local num = Common.num
local truthy = Common.truthy
local signedMod = Common.signedMod
local spellDuration = Common.spellDuration
local spellName = Common.spellName
local spellLink = Common.spellLink

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

-- Item/SpellDetails reproduction --------------------------------------------

local function imageFile(name)
	if isBlank(name) then
		return nil
	end
	local file = tostring(name)
	if not file:match("%.%a+$") then
		file = file .. ".png"
	end
	return file
end

-- Stat modifier rows, in the live Item/SpellDetails order. Rendered "Label +N"
-- (green) / "-N" (red); resists/haste/lifesteal carry a suffix.
-- Item proc-detail mod suffixes (haste/lifesteal render as %); the Resonance row
-- is appended after the shared list, matching the live Item/SpellDetails.
local ITEM_MOD_SUFFIX = { haste = "%", lifesteal = "%" }

local SPELL_FLAGS = {
	{ key = "lifetap", label = "Lifetap" },
	{ key = "groupEffect", label = "Group Effect" },
	{ key = "stun", label = "Stuns Target" },
	{ key = "charm", label = "Charms Target" },
	{ key = "root", label = "Roots Target" },
}

-- Reproduce Template:Item/SpellDetails for the spell at `stableKey`.
-- opts = { worn = bool, procHeader = string }.
local function spellDetails(stableKey, opts)
	if isBlank(stableKey) then
		return nil
	end
	local spell = SpellData.spells[stableKey]
	if spell == nil then
		return nil
	end
	opts = opts or {}
	local root = mw.html.create("div"):addClass("item-spell-details")

	local headerRow = root:tag("div"):addClass("item-spell-details-header-row")
	local icon = imageFile(spell.image)
	if icon ~= nil then
		headerRow
			:tag("div")
			:addClass("item-spell-details-icon")
			:wikitext("[[File:" .. icon .. "|48px]]")
	end
	local nameCell = headerRow:tag("div"):addClass("item-spell-details-name-cell")
	if not isBlank(opts.procHeader) then
		nameCell:tag("div"):addClass("item-spell-details-proc-header"):wikitext(opts.procHeader)
	end
	nameCell
		:tag("div")
		:addClass("item-spell-details-header")
		:wikitext(spellLink(stableKey) or "Spell Effect")
	if icon ~= nil then
		headerRow:tag("div"):addClass("item-spell-details-spacer")
	end

	local content = root:tag("div"):addClass("item-spell-details-content")
	content
		:tag("div")
		:addClass("item-spell-detail-row")
		:addClass("item-spell-level")
		:wikitext("Spell Level: " .. num(spell.requiredLevel))
	content
		:tag("div")
		:addClass("item-spell-detail-row")
		:addClass("item-spell-duration")
		:wikitext(spellDuration(spell))
	content
		:tag("div")
		:addClass("item-spell-detail-row")
		:wikitext("Spell Type: " .. (spell.type or ""))
	content
		:tag("div")
		:addClass("item-spell-detail-row")
		:wikitext("Spell Line: " .. (spell.line or ""))

	local perTick = (tonumber(spell.durationTicks) or 0) > 0 and " / tick" or ""
	if truthy(spell.targetDamage) then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:addClass("item-spell-damage")
			:wikitext("Damage: " .. spell.targetDamage .. perTick)
	end
	if truthy(spell.targetHealing) then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:addClass("item-spell-healing")
			:wikitext("Healing: " .. spell.targetHealing .. perTick)
	end
	if truthy(spell.shieldAmount) then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:addClass("item-spell-positive")
			:wikitext("Shield Amount: " .. spell.shieldAmount)
	end
	if opts.worn ~= true then
		local castTicks = tonumber(spell.castTimeTicks)
		if castTicks ~= nil and castTicks > 0 then
			content
				:tag("div")
				:addClass("item-spell-detail-row")
				:wikitext(string.format("Cast Time: %.1f sec", castTicks / 60))
		end
	end
	if
		not isBlank(spell.damageType)
		and (truthy(spell.targetDamage) or spell.type == "StatusEffect" or truthy(spell.taunt))
	then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:wikitext("Resist Type: " .. spell.damageType)
	end
	for _, flag in ipairs(SPELL_FLAGS) do
		if truthy(spell[flag.key]) then
			content
				:tag("div")
				:addClass("item-spell-detail-row")
				:addClass("item-spell-flag")
				:wikitext(flag.label)
		end
	end
	if truthy(spell.taunt) then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:addClass("item-spell-flag")
			:wikitext("Taunt: " .. num(spell.aggro) .. " aggro")
	end
	local statusName = spellName(spell.statusEffectStableKey)
	if not isBlank(statusName) then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:addClass("item-spell-flag")
			:wikitext("Apply Effects on Target: " .. statusName)
	end
	for _, mod in ipairs(Common.STAT_MODS) do
		if num(spell[mod.key]) ~= 0 then
			content
				:tag("div")
				:addClass("item-spell-detail-row")
				:wikitext(mod.label .. " " .. signedMod(spell[mod.key], ITEM_MOD_SUFFIX[mod.key]))
		end
	end
	if num(spell.resonance) ~= 0 then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:wikitext("Resonance " .. signedMod(spell.resonance))
	end
	local addProcName = spellName(spell.addProcStableKey)
	if not isBlank(addProcName) then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:wikitext(num(spell.addProcChance) .. "% chance to proc " .. addProcName)
	end
	if not isBlank(spell.specialDescriptor) then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:addClass("item-spell-special")
			:wikitext(spell.specialDescriptor)
	end
	if truthy(spell.xpBonus) then
		content
			:tag("div")
			:addClass("item-spell-detail-row")
			:addClass("item-spell-positive")
			:wikitext("XP Bonus: +" .. spell.xpBonus .. "%")
	end
	return tostring(root)
end

-- Game-authoritative weapon proc trigger (ItemInfoWindow.cs:446-460): shields
-- bash, bracers cast, otherwise attack; wand/bow effects always attack.
local function weaponEffect(item)
	if not isBlank(item.weaponProc) then
		local style = "ATTACK"
		if item.shield then
			style = "BASH"
		elseif item.slot == "Bracer" then
			style = "CAST"
		end
		return item.weaponProc, num(item.weaponProcChance) .. "% chance on " .. style .. ":"
	end
	if not isBlank(item.wandEffect) then
		return item.wandEffect, num(item.wandProcChance) .. "% chance on ATTACK:"
	end
	if not isBlank(item.bowEffect) then
		return item.bowEffect, num(item.bowProcChance) .. "% chance on ATTACK:"
	end
	return nil
end

-- Weapon type line, matching the game (ItemInfoWindow): "Slot: <slot>" with a
-- " - 2-Handed" suffix for true 2-handed weapons, except PrimaryOrSecondary which
-- the game prints without the "Slot:" prefix. Linked to the Weapons section.
local function weaponTypeLine(item)
	local slot = slotDisplay(item)
	if slot == nil then
		return nil
	end
	if TWO_HANDED[item.weaponType] then
		slot = slot .. " - 2-Handed"
	end
	local line = "[[Weapons#" .. slot .. "|" .. slot .. "]]"
	if item.slot ~= "PrimaryOrSecondary" then
		line = "Slot: " .. line
	end
	return line .. relicSuffix(item)
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
		-- The game shows range for every weapon: wand range, bow range, else 1.
		local range = 1
		if item.wand and not isBlank(item.wandRange) then
			range = item.wandRange
		elseif item.bow and not isBlank(item.bowRange) then
			range = item.bowRange
		end
		statRow(column, "Range", tostring(range))
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
	local details = ""
	if weapon then
		local effectKey, procHeader = weaponEffect(item)
		if effectKey ~= nil then
			details = spellDetails(effectKey, { worn = false, procHeader = procHeader }) or ""
		end
	elseif not isBlank(item.wornEffect) then
		details = spellDetails(item.wornEffect, { worn = true, procHeader = "Worn Effect:" }) or ""
	end
	return tostring(root) .. details
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

-- Charm scaling labels (live Item/CharmScaling, matching ItemInfoWindow.cs):
-- the renamed attributes, "/ 40" scale, mitigation as a percentage.
local CHARM_SCALING = {
	{ label = "Physicality", key = "strScaling", sign = "+", suffix = " / 40" },
	{ label = "Hardiness", key = "endScaling", sign = "+", suffix = " / 40" },
	{ label = "Finesse", key = "dexScaling", sign = "+", suffix = " / 40" },
	{ label = "Defense", key = "agiScaling", sign = "+", suffix = " / 40" },
	{ label = "Arcanism", key = "intScaling", sign = "+", suffix = " / 40" },
	{ label = "Restoration", key = "wisScaling", sign = "+", suffix = " / 40" },
	{ label = "Mind", key = "chaScaling", sign = "+", suffix = " / 40" },
	{ label = "Resist Scaling", key = "resistScaling", sign = "", suffix = " / 40" },
	{ label = "Mitigation Scaling", key = "mitigationScaling", sign = "+", suffix = "%" },
}

local function charmModifiers(stats)
	local parts = { "Class modifiers:" }
	for _, scaling in ipairs(CHARM_SCALING) do
		local value = stats[scaling.key]
		if num(value) ~= 0 then
			parts[#parts + 1] = "<br/>"
				.. scaling.label
				.. ": "
				.. scaling.sign
				.. tostring(value)
				.. scaling.suffix
		end
	end
	return table.concat(parts)
end

local function charmTooltip(item, stats)
	local root, body = tooltipShell(item, tierOf(stats.quality), nil)
	local container = body:tag("div"):addClass("item-tooltip-charm-container")
	container:tag("div"):addClass("item-tooltip-charm-label"):wikitext("Charm Item")
	container:tag("div"):addClass("item-tooltip-charm-modifiers"):wikitext(charmModifiers(stats))
	container:tag("div"):addClass("item-tooltip-charm-explanation"):wikitext(
		"Charms do not increase stats, they modify how effectively your character utilizes stats."
	)
	local classes = classRestrictions(item)
	if classes ~= nil then
		body:node(classes)
	end
	return tostring(root)
end

local function consumableTooltip(item, stats)
	local root, body = tooltipShell(item, tierOf(stats.quality), nil)
	local container = body:tag("div"):addClass("item-tooltip-consumable-container")
	local effectName = spellName(item.clickEffect)
	if not isBlank(effectName) then
		container
			:tag("div")
			:addClass("item-tooltip-consumable-type")
			:wikitext("Activatable: " .. effectName)
	end
	local desc = description(item)
	if desc ~= nil then
		container:node(desc)
	end
	if item.disposable then
		container
			:tag("div")
			:addClass("item-tooltip-consumable-usage")
			:wikitext("Item Consumed Upon Use.")
	end
	container
		:tag("div")
		:addClass("item-tooltip-consumable-usage")
		:wikitext("Right click or assign to hotkey to use.")
	local details = spellDetails(item.clickEffect, { worn = false }) or ""
	return tostring(root) .. details
end

local function generalTooltip(item, stats)
	local root, body = tooltipShell(item, tierOf(stats.quality), nil)
	local desc = description(item)
	if desc ~= nil then
		body:node(desc)
	end
	local effectName = spellName(item.clickEffect)
	if not isBlank(effectName) then
		body:tag("div")
			:addClass("item-tooltip-activatable-name")
			:wikitext("Activatable: " .. effectName)
		local usage = "Right click or assign to hotkey to use."
		if item.disposable then
			usage = usage .. "<br>Item Consumed Upon Use."
		end
		body:tag("div"):addClass("item-tooltip-proc-usage"):wikitext(usage)
	end
	local details = ""
	if not isBlank(effectName) then
		details = spellDetails(item.clickEffect, { worn = false, procHeader = "Activatable:" })
			or ""
	end
	return tostring(root) .. details
end

local function auraTooltip(item, stats)
	local root, body = tooltipShell(item, tierOf(stats.quality), nil)
	local container = body:tag("div"):addClass("item-tooltip-aura-container")
	container:tag("div"):addClass("item-tooltip-aura-type"):wikitext("Aura Item")
	local notes = container:tag("div"):addClass("item-tooltip-aura-notes")
	notes:tag("div"):wikitext("Auras effect entire party")
	notes:tag("div"):wikitext("Auras of same type do not stack")
	local auraName = spellName(item.aura)
	if not isBlank(auraName) then
		container:tag("div"):addClass("item-tooltip-aura-spell-name"):wikitext(auraName)
		local auraSpell = SpellData.spells[item.aura]
		if auraSpell ~= nil and not isBlank(auraSpell.description) then
			container
				:tag("div")
				:addClass("item-tooltip-aura-spell-desc")
				:wikitext(Format.escape(auraSpell.description))
		end
	end
	local details = spellDetails(item.aura, { worn = true }) or ""
	return tostring(root) .. details
end

local function craftingList(entries)
	return table.concat(entries, "<br/>")
end

local function moldTooltip(item, stats)
	local root, body = tooltipShell(item, tierOf(stats.quality), nil)
	local container = body:tag("div"):addClass("item-tooltip-crafting-container")
	if item.ingredients ~= nil and #item.ingredients > 0 then
		local ingredients = container:tag("div"):addClass("item-tooltip-crafting-ingredients")
		ingredients:tag("div"):addClass("item-tooltip-crafting-header"):wikitext("Ingredients:")
		ingredients:wikitext(craftingList(item.ingredients))
	end
	if item.rewards ~= nil and #item.rewards > 0 then
		local rewards = container:tag("div"):addClass("item-tooltip-crafting-rewards")
		rewards:tag("div"):addClass("item-tooltip-crafting-header"):wikitext("Creates:")
		rewards:wikitext(craftingList(item.rewards))
	end
	local notes = container:tag("div"):addClass("item-tooltip-crafting-notes")
	notes:tag("div"):wikitext("Note: Ingredients MUST be exact quantities")
	notes:tag("div"):wikitext("Use CTRL + CLICK to separate stacks.")
	return tostring(root)
end

-- Shared book/scroll container: "Required Level:" + per-class levels; the caller
-- appends type-specific detail and description rows.
local function bookRequirements(body)
	local container = body:tag("div"):addClass("item-tooltip-book-container")
	container:tag("div"):addClass("item-tooltip-book-requirement"):wikitext("Required Level:")
	return container:tag("div"):addClass("item-tooltip-book-class-requirements")
end

local function classReq(reqs, label, level)
	reqs:tag("div"):addClass("item-tooltip-book-class-req"):wikitext(label .. ": " .. level)
end

local function publicSkillType(skillType)
	if skillType == "Innate" then
		return "Passive"
	end
	return skillType
end
-- SkillBook: the taught skill's per-class required levels (display names come
-- from the data, Duelist→Windblade), skill type, description, and the SimPlayers
-- auto-learn warning.
local function skillBookTooltip(item, stats)
	local root, body = tooltipShell(item, tierOf(stats.quality), nil)
	local reqs = bookRequirements(body)
	local skill = SkillData.skills[item.teachesSkill]
	if skill ~= nil then
		local levelByClass = {}
		for _, entry in ipairs(skill.classLevels or {}) do
			levelByClass[entry.displayName] = entry.level
		end
		for _, class in ipairs(CLASS_ORDER) do
			if levelByClass[class] ~= nil then
				classReq(reqs, class, levelByClass[class])
			end
		end
		local skillType = publicSkillType(skill.type)
		if not isBlank(skillType) then
			reqs:tag("div")
				:addClass("item-tooltip-book-detail")
				:wikitext("Skill Type: " .. skillType)
		end
		if not isBlank(skill.description) then
			reqs:tag("div")
				:addClass("item-tooltip-book-description")
				:wikitext(Format.escape(skill.description))
		end
		if skill.simPlayersAutolearn == false then
			reqs:tag("div"):addClass("item-tooltip-book-warning"):wikitext(
				"SimPlayers DO NOT automatically learn this skill!<br/>Hand this book to them to allow them to use it."
			)
		end
	end
	return tostring(root)
end

local CLASS_INTERNAL_ALIAS = { Windblade = "Duelist" }

-- SpellScroll: the taught spell's required level for each usable class, mana
-- cost, spell type, and description.
local function spellScrollTooltip(item, stats)
	local root, body = tooltipShell(item, tierOf(stats.quality), nil)
	local reqs = bookRequirements(body)
	local spell = SpellData.spells[item.teachesSpell]
	if spell ~= nil then
		local usable = {}
		for _, class in ipairs(spell.classes or {}) do
			usable[class] = true
		end
		local level = num(spell.requiredLevel)
		for _, class in ipairs(CLASS_ORDER) do
			if usable[class] or usable[CLASS_INTERNAL_ALIAS[class]] then
				classReq(reqs, class, level)
			end
		end
		if num(spell.manaCost) ~= 0 then
			reqs:tag("div")
				:addClass("item-tooltip-book-detail")
				:wikitext("Mana Cost: " .. spell.manaCost)
		end
		if not isBlank(spell.type) then
			reqs:tag("div")
				:addClass("item-tooltip-book-detail")
				:wikitext("Spell Type: " .. spell.type)
		end
		if not isBlank(spell.description) then
			reqs:tag("div")
				:addClass("item-tooltip-book-description")
				:wikitext(Format.escape(spell.description))
		end
	end
	return tostring(root)
end

local function renderQuality(item, stats)
	local kind = item.type
	if kind == "Weapon" then
		return gearTooltip(item, stats, true, weaponTypeLine(item))
	elseif kind == "Armor" then
		return gearTooltip(item, stats, false, armorTypeLine(item))
	elseif kind == "Charm" then
		return charmTooltip(item, stats)
	elseif kind == "Consumable" then
		return consumableTooltip(item, stats)
	elseif kind == "General" then
		return generalTooltip(item, stats)
	elseif kind == "Aura" then
		return auraTooltip(item, stats)
	elseif kind == "Mold" then
		return moldTooltip(item, stats)
	elseif kind == "Skill Book" then
		return skillBookTooltip(item, stats)
	elseif kind == "Spell Scroll" then
		return spellScrollTooltip(item, stats)
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

local ITEM_TYPE_CATEGORY = {
	Weapon = "weapon",
	Armor = "armor",
	Charm = "charm",
	Consumable = "consumable",
	General = "general",
	Aura = "aura",
	Mold = "mold",
	["Skill Book"] = "skillbook",
	["Spell Scroll"] = "spellscroll",
}

local WEAPON_TYPE_CATEGORY = {
	["Primary - 2-Handed"] = "2-Handed Weapons",
	["Primary"] = "Primary Weapons",
	["Primary or Secondary"] = "Primary or Secondary Weapons",
	["Secondary"] = "Off-Hand Equipment",
}

local ARMOR_SLOT_CATEGORY = {
	Charm = "Charms",
	Head = "Head Armor",
	Neck = "Neck Items",
	Ring = "Ring Items",
	Hand = "Hand Armor",
	Chest = "Chest Armor",
	Arm = "Arm Armor",
	Bracer = "Bracer Armor",
	Leg = "Leg Armor",
	Waist = "Waist Armor",
	Foot = "Foot Armor",
	Back = "Back Items",
}

local function category(name)
	return "[[Category:" .. name .. "]]"
end

local function weaponTypeLabel(item)
	local slot = slotDisplay(item)
	if slot == nil then
		return nil
	end
	if TWO_HANDED[item.weaponType] then
		return slot .. " - 2-Handed"
	end
	return slot
end

-- Spell-effect buckets (subcategories of Items with Spell Effects). Consumables
-- are intentionally excluded, matching the live template.
local function spellEffectCategories(item)
	local out = {}
	local function add(name)
		out[#out + 1] = category(name)
	end
	if item.type == "Weapon" or item.type == "Armor" then
		if not isBlank(item.clickEffect) then
			add("Activatable Items")
			add("Items with Spell Effects")
		elseif not isBlank(item.wornEffect) then
			add("Worn Effect Items")
			add("Items with Spell Effects")
		elseif
			not isBlank(item.weaponProc)
			or not isBlank(item.wandEffect)
			or not isBlank(item.bowEffect)
		then
			add("Proc Items")
			add("Items with Spell Effects")
		end
	elseif item.type == "General" then
		if not isBlank(item.clickEffect) then
			add("Activatable Items")
			add("Items with Spell Effects")
		end
	elseif item.type == "Aura" then
		if not isBlank(item.aura) then
			add("Items with Spell Effects")
		end
	end
	return table.concat(out)
end

-- Tracking categories (main namespace only), reproducing Template:Item/Categories.
local function itemCategories(item)
	local title = mw.title.getCurrentTitle()
	if title == nil or title.namespace ~= 0 then
		return ""
	end
	local kind = ITEM_TYPE_CATEGORY[item.type]
	if kind == nil then
		return ""
	end
	local parts = {}
	local function add(name)
		parts[#parts + 1] = category(name)
	end
	if kind == "weapon" then
		add("Weapons")
		local range = (item.wand and item.wandRange) or (item.bow and item.bowRange) or nil
		if range ~= nil and num(range) > 1 then
			add("Ranged Weapons")
		end
		local label = weaponTypeLabel(item)
		if label ~= nil and WEAPON_TYPE_CATEGORY[label] ~= nil then
			add(WEAPON_TYPE_CATEGORY[label])
		end
	elseif kind == "armor" then
		add("Armor")
		if item.slot ~= nil and ARMOR_SLOT_CATEGORY[item.slot] ~= nil then
			add(ARMOR_SLOT_CATEGORY[item.slot])
		end
	elseif kind == "charm" then
		add("Charms")
	elseif kind == "consumable" then
		add("Consumables")
	elseif kind == "spellscroll" then
		add("Ability Books")
		add("Spell Scrolls")
	elseif kind == "skillbook" then
		add("Ability Books")
		add("Skill Books")
	elseif kind == "aura" then
		add("Auras")
	elseif kind == "mold" then
		add("Molds")
	elseif kind == "general" then
		add("Items")
	end
	return table.concat(parts) .. spellEffectCategories(item)
end

-- Build the full tooltip wikitext for a resolved item. Weapons and armor render
-- one tooltip per quality (distinguished by name color); other items render one.
function Tooltip.render(item)
	local stats = orderedStats(item)
	local body
	if #stats <= 1 then
		body = renderQuality(item, stats[1] or { quality = "Normal" })
	else
		local wrapper = mw.html
			.create("div")
			:addClass("item-tooltip-quality-set")
			:css("display", "flex")
			:css("flex-wrap", "wrap")
			:css("gap", "1em")
			:css("align-items", "flex-start")
			:css("width", "calc(100% - 360px)")
			:css("min-width", "350px")
			:css("max-width", "100%")
			:css("overflow", "visible")
		for _, row in ipairs(stats) do
			wrapper
				:tag("div")
				:addClass("item-tooltip-quality")
				:css("flex", "0 1 350px")
				:wikitext(renderQuality(item, row))
		end
		body = tostring(wrapper)
	end
	return body .. itemCategories(item)
end

return Tooltip
