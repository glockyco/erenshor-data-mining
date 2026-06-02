# Erenshor Lua modules

This directory is the git source of truth for Erenshor wiki Scribunto modules.

Files here deploy to the wiki `Module:` namespace. For example:

```text
wiki/modules/Erenshor/Item.lua       -> Module:Erenshor/Item
wiki/modules/Erenshor/Data/Items.lua -> Module:Erenshor/Data/Items
```

Generated data modules should be deterministic and contain only values supported by
`mw.loadData()`: strings, numbers, booleans, and tables. Display modules should keep
public `p.<name>(frame)` entry points thin and put testable logic in private helpers
that ScribuntoUnit testcases can call.
