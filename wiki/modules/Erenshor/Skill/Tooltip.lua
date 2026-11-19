-- Module:Erenshor/Skill/Tooltip
--
-- The compact card follows the hotkey's ability card. Stance abilities still
-- link to the stance and describe what changes when it is activated.

local Common = require("Module:Erenshor/Ability/Common")
local Format = require("Module:Erenshor/Format")

local StanceData = mw.loadData("Module:Erenshor/Data/Stances")

local Tooltip = {}

local function detailRow(content, text, class)
	local row = content:tag("div"):addClass("item-spell-detail-row")
	if class ~= nil then
		row:addClass(class)
	end
	row:wikitext(text)
	return row
end

-- Build the tooltip DOM for a resolved skill record. Identity defaults to the
-- skill's own stable key, while stance tooltips reuse this renderer with a stance
-- identity so the card links to the stance entity.
function Tooltip.render(skill, identity)
	identity = identity or { kind = "skill", stableKey = skill.stableKey }
	local root = Common.standaloneTooltipRoot(identity.kind, identity.stableKey)
	Common.bookHeader(root, skill.name or "Skill", "Ability")
	local content = root:tag("div"):addClass("item-ability-description")

	local stance = nil
	if not Common.isBlank(skill.stanceStableKey) then
		stance = StanceData.stances[skill.stanceStableKey]
	end

	if stance ~= nil then
		detailRow(content, "Change Stance")
		detailRow(content, Format.pageLink(stance.page, stance.name), "item-spell-details-header")
		detailRow(content, Format.escape(stance.description or ""))
	else
		detailRow(content, Format.escape(skill.description or ""))
	end

	return tostring(root)
end

return Tooltip
