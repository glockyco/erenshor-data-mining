-- Module:Erenshor/Skill/Tooltip
--
-- Skills use the hotkey text. Stance entities use the activating skillbook.

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

local function descriptionRows(content, description)
	for line in (description or ""):gmatch("[^\r\n]+") do
		detailRow(content, Format.escape(line))
	end
end

-- Build the tooltip DOM for a resolved skill record. Identity defaults to the
-- skill's own stable key, while stance tooltips reuse this renderer with a stance
-- identity so the card links to the stance entity.
function Tooltip.render(skill, identity)
	identity = identity or { kind = "skill", stableKey = skill.stableKey }
	local root = Common.standaloneTooltipRoot(identity.kind, identity.stableKey)
	local stanceCard = identity.kind == "stance"
	local header = skill.name or "Skill"
	if stanceCard then
		header = header .. " - Activatable"
	end
	Common.bookHeader(root, header, stanceCard and "" or "Ability")
	local content = root:tag("div"):addClass("item-ability-description")

	local stance = nil
	if stanceCard and not Common.isBlank(skill.stanceStableKey) then
		stance = StanceData.stances[skill.stanceStableKey]
	end

	if stance ~= nil then
		detailRow(content, "Change Stance")
		local name = skill.stanceStableKey == "stance:normal" and "normal" or stance.name
		detailRow(content, Format.pageLink(stance.page, name), "item-spell-details-header")
		descriptionRows(content, stance.description)
	else
		descriptionRows(content, skill.description)
	end

	return Format.preserveIdentityAttributes(root)
end

return Tooltip
