-- Module:Erenshor/Spell/Tooltip
--
-- Presentation layer for the spell tooltip. Reproduces the in-game spellbook
-- tooltip (SpellbookSlot.cs:150-275) row-for-row, reusing the item tooltip's
-- `item-spell-*` CSS classes so spell pages look like the game.
--
-- Faithfulness: content, order, labels, colors, and which rows appear match the
-- game. Permitted convenience: the applied status effect renders as a link.

local Common = require("Module:Erenshor/Ability/Common")

local Tooltip = {}

-- Flags shown in the game's tooltip blue block, in SpellbookSlot order.
local FLAGS = {
	{ key = "lifetap", label = "Lifetap" },
	{ key = "groupEffect", label = "Group Effect" },
	{ key = "stun", label = "Stuns Target" },
	{ key = "charm", label = "Charms Target" },
	{ key = "root", label = "Roots Target" },
}

-- Stat-modifier percent suffixes for the spell tooltip (SpellbookSlot: only
-- lifesteal carries a %, haste does not).
local MOD_SUFFIX = { lifesteal = "%" }

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

-- Build the tooltip DOM for a resolved spell record.
function Tooltip.render(spell)
	-- Standalone tooltips opt into a top border (the embedded item case inherits its
	-- top edge from the item tooltip's divider). Styled by Gadget:erenshor.css.
	local root = mw.html
		.create("div")
		:addClass("item-spell-details")
		:addClass("item-spell-details-standalone")

	local headerRow = root:tag("div"):addClass("item-spell-details-header-row")
	local hasIcon = not Common.isBlank(spell.image)
	if hasIcon then
		headerRow
			:tag("div")
			:addClass("item-spell-details-icon")
			:wikitext("[[File:" .. tostring(spell.image) .. ".png|48px]]")
	end
	headerRow
		:tag("div")
		:addClass("item-spell-details-name-cell")
		:tag("div")
		:addClass("item-spell-details-header")
		:wikitext(spell.name or "Spell")
	-- Balance the fixed-width icon so the title centers in the full width.
	if hasIcon then
		headerRow:tag("div"):addClass("item-spell-details-spacer")
	end

	local content = root:tag("div"):addClass("item-spell-details-content")

	detailRow(content, Common.spellDuration(spell), "item-spell-duration")
	detailRow(content, "Spell Type: " .. (spell.type or ""))
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

	if not Common.isBlank(spell.specialDescriptor) then
		detailRow(content, spell.specialDescriptor, "item-spell-special")
	end

	return tostring(root)
end

return Tooltip
