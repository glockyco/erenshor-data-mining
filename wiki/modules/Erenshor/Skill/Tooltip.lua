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

-- Build the tooltip DOM for a resolved skill record.
function Tooltip.render(skill)
	-- SkillbookSlot.cs:146 — Activatable unless the skill is Innate.
	local kind = (skill.type ~= "Innate") and "Activatable" or "Passive"

	-- Standalone tooltips need a top border (`.item-spell-details` sets border-top: none
	-- for the embedded item case, where the item tooltip's divider sits above it).
	local root =
		mw.html.create("div"):addClass("item-spell-details"):css("border-top", "2px solid #d0d0d0")
	root:tag("div")
		:addClass("item-spell-details-header-row")
		:tag("div")
		:addClass("item-spell-details-name-cell")
		:tag("div")
		:addClass("item-spell-details-header")
		:wikitext((skill.name or "Skill") .. " - " .. kind)

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
