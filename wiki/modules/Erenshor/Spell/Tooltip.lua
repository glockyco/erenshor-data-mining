-- Module:Erenshor/Spell/Tooltip
--
-- Spell articles show the compact hotkey or Bard song card and the standalone
-- item spell-details card. Link previews reuse the details card.

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

-- Cast time uses one-decimal formatting (ItemInfoWindow.cs:680 ToString("F1")),
-- the clean game convention, rather than the raw float SpellbookSlot prints.
local function castSeconds(seconds)
	local tenths = math.floor(Common.num(seconds) * 10 + 0.5)
	return string.format("%.1f", tenths / 10) .. " sec"
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
	local song = Common.truthy(spell.bardSong)
	local root = mw.html.create("div"):addClass("item-spell-details item-spell-details-standalone")
	Common.bookHeader(
		root,
		spell.gameName or spell.name or "Spell",
		song and "Bard Song" or "Spell"
	)
	if not Common.isBlank(spell.description) then
		root:tag("div")
			:addClass("item-ability-description")
			:wikitext(Format.escape(spell.description))
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
	local root = panel
		:tag("div")
		:addClass("erenshor-ability-tooltip item-spell-details")
		:attr("data-erenshor-kind", "spell")
		:attr("data-erenshor-key", spell.stableKey)
	local header = root:tag("div"):addClass("item-spell-details-header-row")
	local hasIcon = not Common.isBlank(spell.icon)
	if hasIcon then
		header:tag("div"):addClass("item-spell-details-icon"):wikitext(
			Icon.render(mw.getCurrentFrame(), { file = spell.icon, kind = "ability", size = 48 })
		)
	end
	header
		:tag("div")
		:addClass("item-spell-details-name-cell")
		:tag("div")
		:addClass("item-spell-details-header")
		:wikitext(Format.escape(spell.gameName or spell.name or "Spell"))
	if hasIcon then
		header:tag("div"):addClass("item-spell-details-spacer")
	end
	local content = root:tag("div"):addClass("item-spell-details-content item-spell-window-lines")

	detailRow(content, "Spell Level: " .. Common.num(spell.requiredLevel), "item-spell-level")
	detailRow(content, Common.spellDuration(spell), "item-spell-duration")
	detailRow(content, "Spell Type: " .. (spell.type or ""))
	if not Common.isBlank(spell.line) then
		detailRow(content, "Spell Line: " .. spell.line)
	end

	if Common.truthy(spell.targetDamage) then
		local perTick = (Common.num(spell.durationSeconds) > 0) and " / 3 sec" or ""
		detailRow(
			content,
			'<span class="item-spell-damage">Damage: ' .. spell.targetDamage .. "</span>" .. perTick
		)
	end

	detailRow(content, "Cast Time: " .. castSeconds(spell.castTimeSeconds))

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
			detailRow(content, flag.label, "item-spell-window-flag")
		end
	end
	if Common.truthy(spell.taunt) then
		detailRow(
			content,
			'<span class="item-spell-window-flag">Taunt:</span> '
				.. Common.num(spell.aggro)
				.. " aggro"
		)
	end

	local statusLink = Common.spellLink(spell.statusEffectStableKey)
	if not Common.isBlank(statusLink) then
		detailRow(content, "Apply Effects on Target", "item-spell-window-flag")
		detailRow(content, "-" .. statusLink)
	end

	for _, mod in ipairs(Common.STAT_MODS) do
		if
			Common.num(spell[mod.key]) ~= 0
			and (mod.key ~= "mana" or not Common.truthy(spell.levelScaledManaRestoration))
		then
			local name = mod.key == "mana" and "Mana Regen" or mod.label
			detailRow(
				content,
				name .. " " .. Common.signedMod(spell[mod.key]) .. (MOD_SUFFIX[mod.key] or "")
			)
		end
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

	return Format.preserveIdentityAttributes(panel)
end

return Tooltip
