local Args = require("Module:Erenshor/Args")

local p = {}

local function assertEqual(actual, expected, label)
	if actual ~= expected then
		error(
			string.format("%s: expected %s, got %s", label, tostring(expected), tostring(actual)),
			2
		)
	end
end

function p.run()
	assertEqual(Args.trim("  Ember  "), "Ember", "trim removes edge whitespace")
	assertEqual(Args.trim(nil), nil, "trim preserves nil")
	assertEqual(Args.isBlank(" \t\n "), true, "whitespace is blank")
	assertEqual(Args.has({ name = "" }, "name"), true, "empty arg is explicitly present")
	assertEqual(Args.has({}, "name"), false, "missing arg is not explicitly present")
	assertEqual(
		Args.resolve({ name = " Override " }, "name", "Generated"),
		"Override",
		"explicit value overrides default"
	)
	assertEqual(
		Args.resolve({ name = "" }, "name", "Generated"),
		"Generated",
		"blank value falls back to default"
	)
	assertEqual(
		Args.resolve({ name = "-" }, "name", "Generated"),
		nil,
		"dash sentinel intentionally blanks default"
	)
	assertEqual(Args.bool({ relic = "yes" }, "relic", false), true, "yes parses as true")
	assertEqual(Args.bool({ relic = "0" }, "relic", true), false, "zero parses as false")
	assertEqual(Args.bool({ relic = "-" }, "relic", true), nil, "dash sentinel blanks booleans")
	assertEqual(Args.number({ level = " 12 " }, "level", 1), 12, "numeric value parses")
	assertEqual(Args.number({ level = "" }, "level", 1), 1, "blank number falls back to default")

	return "PASS Erenshor Args testcases"
end

return p
