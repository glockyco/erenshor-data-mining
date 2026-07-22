-- Module:Erenshor/Skill/Tooltip
--
-- Presentation layer for the skill tooltip. Reproduces the in-game skillbook
-- tooltip (SkillbookSlot.cs:146-156): the title is "<name> - Activatable" for any
-- non-Innate skill (else "- Passive"), the body is the skill description, or the
-- "Change Stance" block (stance name + description) for stance-switching skills.
-- Reuses the item tooltip's `item-spell-*` CSS so skill pages look like the game.
--
-- Permitted convenience: the stance renders as a link to its page.

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
	-- SkillbookSlot.cs:146 — Activatable unless the skill is Innate.
	local activation = (skill.type ~= "Innate") and "Activatable" or "Passive"

	-- Standalone tooltips opt into a top border (the embedded item case inherits its
	-- top edge from the item tooltip's divider). Styled by Gadget:erenshor.css.
	-- Common validates both values and rejects unsupported identity kinds.
	local root = Common.standaloneTooltipRoot(identity.kind, identity.stableKey)
	root:tag("div")
		:addClass("item-spell-details-header-row")
		:tag("div")
		:addClass("item-spell-details-name-cell")
		:tag("div")
		:addClass("item-spell-details-header")
		:wikitext((skill.name or "Skill") .. " - " .. activation)

	local content = root:tag("div"):addClass("item-spell-details-content")

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
