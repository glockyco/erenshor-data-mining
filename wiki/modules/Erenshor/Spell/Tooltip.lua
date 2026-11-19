-- Module:Erenshor/Spell/Tooltip
--
-- The compact card follows the hotkey or Bard song hover window. The article
-- also keeps the mechanical rows from the spellbook and item detail windows.

local Common = require("Module:Erenshor/Ability/Common")
local Format = require("Module:Erenshor/Format")
local Icon = require("Module:Erenshor/Icon")

local Tooltip = {}

-- Flags shown in the game's tooltip blue block, in SpellbookSlot order.
local FLAGS = {
	{ key = "lifetap", label = "Lifetap" },
	{ key = "groupEffect", label = "Group Effect" },
	{ key = "stun", label = "Stuns Target" },
	{ key = "charm", label = "Charms Target" },
	{ key = "root", label = "Roots Target" },
}

-- Stat-modifier percent suffixes follow the item's spell-details window.
local MOD_SUFFIX = { lifesteal = "%", haste = "%" }

-- "X sec" with C#-style number formatting (2.0 -> "2", 1.5 -> "1.5").
local function seconds(value)
	return tostring(Common.num(value)) .. " sec"
end

-- Cast time uses one-decimal formatting (ItemInfoWindow.cs:680 ToString("F1")),
-- the clean game convention, rather than the raw float SpellbookSlot prints.
local function castSeconds(seconds)
	return string.format("%.1f", Common.num(seconds)) .. " sec"
end

local function detailRow(content, text, class)
	local row = content:tag("div"):addClass("item-spell-detail-row")
	if class ~= nil then
		row:addClass(class)
	end
	row:wikitext(text)
	return row
end

function Tooltip.render(spell)
	local song = (spell.type or ""):match("^Song") ~= nil
	local root = Common.standaloneTooltipRoot("spell", spell.stableKey)
	Common.bookHeader(root, spell.name or "Spell", song and "Bard Song" or "Spell")
	if not Common.isBlank(spell.description) then
		root:tag("div")
			:addClass("item-ability-description")
			:wikitext(Format.escape(Format.damageOverTimeText(spell.description)))
	end
	local footer = root:tag("div"):addClass("item-ability-footer")
	footer:tag("div"):wikitext("Mana Cost: " .. Common.num(spell.manaCost))
	if not Common.isBlank(spell.damageType) then
		local label = song and "Song Type: " or "Spell Type: "
		footer:tag("div"):wikitext(label .. Format.escape(spell.damageType))
	end
	return tostring(root)
end

function Tooltip.renderPage(spell)
	local panel = mw.html.create("div"):addClass("item-ability-panel")
	panel:wikitext(Tooltip.render(spell))
	local disclosure =
		panel:tag("div"):addClass("item-ability-disclosure mw-collapsible mw-collapsed")
	disclosure:tag("div"):addClass("item-ability-disclosure-label"):wikitext("Spell details")
	local root = disclosure:tag("div"):addClass("item-spell-details mw-collapsible-content")
	if not Common.isBlank(spell.icon) then
		root:tag("div")
			:addClass("item-spell-details-header-row")
			:tag("div")
			:addClass("item-spell-details-icon")
			:wikitext(
				Icon.render(
					mw.getCurrentFrame(),
					{ file = spell.icon, kind = "ability", size = 48 }
				)
			)
	end
	local content = root:tag("div"):addClass("item-spell-details-content")

	detailRow(content, "Spell Level: " .. Common.num(spell.requiredLevel), "item-spell-level")
	detailRow(content, Common.spellDuration(spell), "item-spell-duration")
	detailRow(content, "Spell Type: " .. (spell.type or ""))
	if not Common.isBlank(spell.line) then
		detailRow(content, "Spell Line: " .. spell.line)
	end
	detailRow(content, "Mana Cost: " .. Common.num(spell.manaCost))

	if Common.truthy(spell.targetDamage) then
		local perTick = (Common.num(spell.durationSeconds) > 0) and " / 3 sec" or ""
		detailRow(content, "Damage: " .. spell.targetDamage .. perTick, "item-spell-damage")
	end

	detailRow(content, "Cast Time: " .. castSeconds(spell.castTimeSeconds))
	detailRow(content, "Cooldown: " .. seconds(spell.cooldownSeconds))

	if
		Common.truthy(spell.targetDamage)
		or spell.type == "StatusEffect"
		or Common.truthy(spell.taunt)
	then
		if not Common.isBlank(spell.damageType) then
			detailRow(content, "Resist Type: " .. Common.colorDamageType(spell.damageType))
		end
	end

	for _, flag in ipairs(FLAGS) do
		if Common.truthy(spell[flag.key]) then
			detailRow(content, flag.label, "item-spell-flag")
		end
	end
	if Common.truthy(spell.taunt) then
		detailRow(content, "Taunt: " .. Common.num(spell.aggro) .. " aggro", "item-spell-flag")
	end

	local statusLink = Common.spellLink(spell.statusEffectStableKey)
	if not Common.isBlank(statusLink) then
		detailRow(content, "Apply Effects on Target: " .. statusLink, "item-spell-flag")
	end

	for _, mod in ipairs(Common.STAT_MODS) do
		if Common.num(spell[mod.key]) ~= 0 then
			detailRow(
				content,
				mod.label .. " " .. Common.signedMod(spell[mod.key], MOD_SUFFIX[mod.key])
			)
		end
	end

	if Common.num(spell.levelScaledManaRestoration) ~= 0 then
		detailRow(
			content,
			"Mana Regen " .. Common.signedMod(spell.levelScaledManaRestoration) .. " per level"
		)
	end
	if Common.num(spell.armorPenPercent) ~= 0 then
		detailRow(content, "Armor Penetration " .. Common.signedMod(spell.armorPenPercent, "%"))
	end
	if Common.num(spell.resonance) ~= 0 then
		detailRow(content, "Resonance " .. Common.signedMod(spell.resonance))
	end
	local addProcLink = Common.spellLink(spell.addProcStableKey)
	if not Common.isBlank(addProcLink) then
		detailRow(content, Common.num(spell.addProcChance) .. "% chance to proc " .. addProcLink)
	end

	if not Common.isBlank(spell.specialDescriptor) then
		detailRow(content, spell.specialDescriptor, "item-spell-special")
	end

	return tostring(panel)
end

return Tooltip
