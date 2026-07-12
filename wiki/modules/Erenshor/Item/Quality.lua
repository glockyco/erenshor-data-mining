-- Module:Erenshor/Item/Quality
--
-- Item quality progression and the game's quality-stat formulas. The wiki
-- receives only the Normal row; this module derives the enabled upgrade rows so
-- a formula change does not require rewriting every item page. The shipped
-- Improved +5 resist omission is corrected to preserve intended progression.

local Quality = {}

-- Release gate: keep Improved variants hidden until the game patch ships.
-- Flip this single value to true for the post-patch wiki refresh.
local IMPROVED_QUALITIES_ENABLED = false

-- Runtime IDs, progression rank, and visual tier are deliberately separate.
-- Runtime IDs are not a power ranking, and the green Improved visual tier is
-- shared by all five Improved qualities.
local QUALITIES = {
	{ name = "Normal", runtimeId = 1, progressionRank = 0, visualTier = 0 },
	{ name = "Improved +1", runtimeId = 11, progressionRank = 1, visualTier = 3 },
	{ name = "Improved +2", runtimeId = 12, progressionRank = 2, visualTier = 4 },
	{ name = "Improved +3", runtimeId = 13, progressionRank = 3, visualTier = 5 },
	{ name = "Improved +4", runtimeId = 14, progressionRank = 4, visualTier = 6 },
	{ name = "Improved +5", runtimeId = 15, progressionRank = 5, visualTier = 7 },
	{ name = "Blessed", runtimeId = 2, progressionRank = 6, visualTier = 1 },
	{ name = "Ascended", runtimeId = 3, progressionRank = 7, visualTier = 2 },
}

local function roundToInt(value)
	-- Unity Mathf.RoundToInt uses banker's rounding for exact half values.
	-- Item stats are non-negative, so this positive-only implementation is
	-- equivalent while remaining compatible with Lua 5.1.
	local lower = math.floor(value)
	local fraction = value - lower
	if fraction < 0.5 then
		return lower
	end
	if fraction > 0.5 then
		return lower + 1
	end
	if math.fmod(lower, 2) == 0 then
		return lower
	end
	return lower + 1
end

local function number(value)
	return tonumber(value) or 0
end

local function max3(a, b, c)
	return math.max(a, math.max(b, c))
end

local function calcStat(base, quality)
	local value = number(base)
	if value <= 0 or quality <= 1 then
		return value
	end
	if quality == 2 then
		return value + roundToInt(value / 3) + 3
	end
	if quality == 3 then
		local blessed = value + roundToInt(value / 3) + 3
		return max3(math.max(2 * value, value + 5), blessed + 5, value + 6)
	end
	if quality >= 11 and quality <= 15 then
		return value + math.min(3, math.floor((quality - 9) / 2))
	end
	return value
end

local function calcHealthMana(base, quality)
	local value = number(base)
	if quality <= 1 then
		return value
	end
	local blessed = value + roundToInt(value / 5) + 30
	local ascended = value + roundToInt(value / 2) + 50
	if quality == 2 then
		return blessed
	end
	if quality == 3 then
		return math.max(ascended, blessed + 1, value + 26)
	end
	if quality > 10 and quality <= 15 then
		return value + 5 * (quality - 10)
	end
	return value
end

local function calcArmor(base, quality)
	local value = number(base)
	if quality <= 1 then
		return value
	end
	local blessed = value + roundToInt(value / 6) + 3
	local ascended = value + roundToInt(value / 2)
	if quality == 2 then
		return blessed
	end
	if quality == 3 then
		return math.max(ascended, blessed + 4, value + 8)
	end
	if quality >= 11 and quality <= 15 then
		-- The game does not create Improved armor from a zero base AC.
		if value <= 0 then
			return value
		end
		return value + quality - 10
	end
	return value
end

local function calcResists(base, quality)
	local value = number(base)
	if quality == 2 then
		return value + roundToInt(value / 3) + 1
	end
	if quality == 3 then
		local blessed = value + roundToInt(value / 3) + 1
		return max3(math.max(2 * value, value + 3), blessed + 1, value + 2)
	end
	-- The shipped predicate accidentally omits runtime quality 15, making
	-- Improved +5 fall back to the Normal resist. Keep the intended
	-- non-decreasing Improved progression in wiki-derived values.
	if quality >= 13 and quality <= 15 then
		return value + 1
	end
	return value
end

local function calcResonance(base, quality)
	local value = number(base)
	if quality == 2 then
		return value + 1
	end
	if quality == 3 then
		return value + 2
	end
	return value
end

local function calcDamage(base, quality)
	local value = number(base)
	if quality <= 1 then
		return value
	end
	if quality == 2 then
		return value + 1
	end
	if quality == 3 then
		return value + 2
	end
	return value
end

local function copyBase(base)
	local out = {}
	for key, value in pairs(base or {}) do
		out[key] = number(value)
	end
	return out
end

local function variant(base, quality)
	local out = copyBase(base)
	out.quality = quality.name
	out.runtimeId = quality.runtimeId
	out.progressionRank = quality.progressionRank
	out.visualTier = quality.visualTier

	for _, key in ipairs({ "str", "end", "dex", "agi", "int", "wis", "cha" }) do
		out[key] = calcStat(base[key], quality.runtimeId)
	end
	for _, key in ipairs({ "hp", "mana" }) do
		out[key] = calcHealthMana(base[key], quality.runtimeId)
	end
	out.ac = calcArmor(base.ac, quality.runtimeId)
	for _, key in ipairs({ "mr", "er", "pr", "vr" }) do
		out[key] = calcResists(base[key], quality.runtimeId)
	end
	out.res = calcResonance(base.res, quality.runtimeId)
	out.weaponDamage = calcDamage(base.weaponDamage, quality.runtimeId)
	return out
end

function Quality.improvedEnabled()
	return IMPROVED_QUALITIES_ENABLED
end

function Quality.isImproved(qualityName)
	return type(qualityName) == "string" and string.sub(qualityName, 1, 9) == "Improved "
end

function Quality.list(includeImproved)
	local showImproved = includeImproved
	if showImproved == nil then
		showImproved = IMPROVED_QUALITIES_ENABLED
	end
	local out = {}
	for _, quality in ipairs(QUALITIES) do
		if showImproved or not Quality.isImproved(quality.name) then
			out[#out + 1] = quality
		end
	end
	return out
end

function Quality.variants(base, includeImproved)
	local showImproved = includeImproved
	if showImproved == nil then
		showImproved = IMPROVED_QUALITIES_ENABLED
	end
	local out = {}
	for _, quality in ipairs(QUALITIES) do
		if showImproved or not Quality.isImproved(quality.name) then
			out[#out + 1] = variant(base or {}, quality)
		end
	end
	return out
end

function Quality.roundToInt(value)
	return roundToInt(number(value))
end

return Quality
