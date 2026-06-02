# Erenshor wiki templates

This directory is the git source of truth for Erenshor wiki templates.

Files here deploy to the wiki `Template:` namespace. For example:

```text
wiki/templates/Item.wiki -> Template:Item
```

Templates should remain thin wrappers around Lua modules. Article-local parameters are
part of the public editor API and should override generated Lua data values in the
corresponding display module.
