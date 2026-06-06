-- Module:Erenshor/Ability/Common
--
-- Shared low-level primitives for the in-game-style tooltips (item proc detail,
-- spell tooltip, skill tooltip). Each consumer owns its content/order, which is
-- authoritative from the decompiled game source; this module only holds the
-- helpers and the canonical stat-modifier list so the surfaces cannot drift.
--
-- Damage-type colors: SpellbookSlot.GetColoredDamageType.
-- signedMod / stat list: SpellbookSlot.cs and Item/SpellDetails.

local Format = require("Module:Erenshor/Format")
local SpellData = mw.loadData("Module:Erenshor/Data/Spells")

local Common = {}

local DAMAGE_COLOR = {
	Physical = "#FFFFFF",
	Magic = "#8080FF",
	Elemental = "#FFA500",
	Poison = "#50C878",
	Void = "#B030B0",
}

-- Canonical stat-modifier rows in game order (SpellbookSlot.cs:196-271). Suffixes
-- differ per surface, so callers supply them; the item proc detail also appends a
-- Resonance row that the spellbook tooltip does not show.
Common.STAT_MODS = {
	{ label = "Hitpoints", key = "hp" },
	{ label = "Armor Class", key = "ac" },
	{ label = "Mana", key = "mana" },
	{ label = "Strength", key = "str" },
	{ label = "Dexterity", key = "dex" },
	{ label = "Endurance", key = "end" },
	{ label = "Agility", key = "agi" },
	{ label = "Wisdom", key = "wis" },
	{ label = "Intelligence", key = "int" },
	{ label = "Charisma", key = "cha" },
	{ label = "Magic Resist", key = "mr" },
	{ label = "Elemental Resist", key = "er" },
	{ label = "Poison Resist", key = "pr" },
	{ label = "Void Resist", key = "vr" },
	{ label = "Movement Speed", key = "movementSpeed" },
	{ label = "Damage Shield", key = "damageShield" },
	{ label = "Haste", key = "haste" },
	{ label = "Lifesteal", key = "lifesteal" },
	{ label = "Attack Roll Modifier", key = "atkRollModifier" },
}

function Common.isBlank(value)
	return value == nil or tostring(value):match("^%s*$") ~= nil
end

function Common.num(value)
	return tonumber(value) or 0
end

function Common.truthy(value)
	return value ~= nil and value ~= false and value ~= 0 and value ~= "0" and value ~= ""
end

-- "+N" green / "-N" red, matching SpellbookSlot.FormatMod and Item/SpellDetails.
function Common.signedMod(value, suffix)
	local n = Common.num(value)
	suffix = suffix or ""
	if n > 0 then
		return '<span class="item-spell-positive">+' .. n .. suffix .. "</span>"
	end
	return '<span class="item-spell-negative">' .. n .. suffix .. "</span>"
end

-- Colored damage-type name (SpellbookSlot.GetColoredDamageType); unknown types
-- fall back to the raw name.
function Common.colorDamageType(damageType)
	if Common.isBlank(damageType) then
		return ""
	end
	local color = DAMAGE_COLOR[damageType]
	if color ~= nil then
		return '<span style="color:' .. color .. '">' .. damageType .. "</span>"
	end
	return tostring(damageType)
end

-- durationSeconds <= 0 -> instant; else labelled "Damage over time:" when the
-- spell deals damage, else "Effect Duration:".
function Common.spellDuration(spell)
	local seconds = tonumber(spell.durationSeconds)
	if seconds == nil or seconds <= 0 then
		return "Instant Effect"
	end
	local label = Common.truthy(spell.targetDamage) and "Damage over time:" or "Effect Duration:"
	return label .. " " .. seconds .. " sec"
end

function Common.spellName(stableKey)
	local spell = SpellData.spells[stableKey]
	if spell == nil then
		return nil
	end
	return spell.name
end

function Common.spellLink(stableKey)
	local spell = SpellData.spells[stableKey]
	if spell == nil then
		return nil
	end
	local link = Format.pageLink(spell.page, spell.name)
	if Common.isBlank(link) then
		return spell.name
	end
	return link
end

return Common
