## Purpose

Defines who owns each kind of page and input on the Erenshor wiki, how generated game data reaches the wiki, and the checks that keep a deploy of repository pages from breaking live pages.

## ADDED Requirements

### Requirement: Generated values live only on bot-owned pages

Generated game data SHALL reach the wiki only through bot-owned pages: the Lua data modules under `Module:Erenshor/Data/` and the Cargo storage pages under `Erenshor Wiki:Cargo/`. After an entity type is converted, each article of that type SHALL hold, for each entity it describes, one call of the type's data-backed template with the entity's stable key, and otherwise only text that people write.

#### Scenario: A game update changes a stat

- **WHEN** a new game build changes the damage of a converted item
- **THEN** the refresh changes the item's data module and its Cargo storage page
- **AND** the refresh changes no article

#### Scenario: A converted article holds no generated value

- **WHEN** an item article is converted
- **THEN** its source holds the item's template call with `stablekey` and the text that people wrote, and no generated field value

### Requirement: Only fields that people own can be overridden

A data-backed template SHALL let an article override only the fields that people own: the image, the image caption, other sources, and the location, and on zone pages also the level, the type, the connections, and the map link. A parameter for any other field SHALL NOT change the rendered value, and the page SHALL join a tracking category that names the parameter.

#### Scenario: An editor sets an owned field

- **WHEN** an item article passes `image=Example.png` to its data-backed template
- **THEN** the infobox shows `Example.png`

#### Scenario: An editor sets a generated field

- **WHEN** an item article passes `damage=99` to its data-backed template
- **THEN** the infobox shows the damage from the data module
- **AND** the page joins the tracking category for parameters that cannot override data

### Requirement: Pages say where their data comes from

A data-backed template SHALL name the game build that its data comes from. For a field whose value the export cannot provide for an entity, it SHALL state that the value is not in the export, instead of leaving the field out or showing a default value.

#### Scenario: A value is missing from the export

- **WHEN** the data module has no value for a field that the entity type has
- **THEN** the rendered field states that the value is not in the export

### Requirement: Refreshes leave people's text alone

After an entity type is converted, a refresh SHALL edit an article of that type only when the set of entities on the page changes, and then SHALL change only the template-call lines. A new entity without an article SHALL get a new page that holds its template call.

#### Scenario: The data of an entity changes

- **WHEN** a game update changes the stats of an entity whose page lists the same entities as before
- **THEN** the refresh does not edit that page

#### Scenario: A variant is added

- **WHEN** a game update adds a second variant to a converted character page
- **THEN** the refresh adds one template call for the new variant
- **AND** every other line of the page stays unchanged

#### Scenario: A new entity appears

- **WHEN** a game update adds an item that has no article
- **THEN** the refresh creates a page that holds the item's template call

### Requirement: Legacy entity templates render only their parameters

`Template:Item`, `Template:Character`, `Template:Ability`, `Template:Stance`, `Template:Quest`, `Template:Zone`, and `Template:MapLink` SHALL render only from the parameters of the call. They SHALL NOT invoke a module and SHALL NOT store a Cargo row. `stablekey` and `lua` SHALL NOT change their output.

#### Scenario: A call passes the old switch

- **WHEN** a page calls `{{Character|stablekey=character:a grizzly bear|lua=1|name=A Grizzly Bear}}`
- **THEN** the page shows the same parameter infobox as the call without `stablekey` and `lua`

#### Scenario: A map link renders without data modules

- **WHEN** a page calls `{{MapLink|zone=Azure}}`
- **THEN** the link points at the interactive map with the selector `zone:Azure`
- **AND** the render loads no generated data module

### Requirement: Repository pages deploy only with their dependencies

Before it writes anything, `wiki deploy-repo-pages` SHALL check each module and template that it would write. It SHALL follow every module that the page loads through `#invoke`, `require`, or `mw.loadData` with a literal title, and the modules those load in turn. A page whose dependency is neither live nor written earlier in the same run SHALL NOT be written. The command SHALL name the page and the missing module. A dry run SHALL report the same result.

#### Scenario: A template needs a missing data module

- **WHEN** a run would write a template that invokes `Module:Erenshor/Zone`, and that module loads `Module:Erenshor/Data/Zones`, which does not exist live
- **THEN** the template is not written
- **AND** the output names the template and `Module:Erenshor/Data/Zones`

#### Scenario: A module and its new data module deploy together

- **WHEN** a run writes a new data module and, later in the same run, a module that loads it
- **THEN** the dependency check passes for that module

### Requirement: Repository pages pass a render check before they are written

Before it writes a module or template that main-namespace pages use, `wiki deploy-repo-pages` SHALL parse a selection of those pages twice on the live wiki: with the live text, and with the new text in its place through TemplateSandbox. By default, the selection SHALL cover every template, every filled template parameter, every `type` and `kind` value, and every entity kind and subtype that occurs on the pages that use it, each at least once. On request, the selection SHALL be every page that uses it. The command SHALL NOT write the page when a parse with the new text shows a script error or a missing template that the live parse does not show. It SHALL report each selected page whose visible text or categories differ. A dry run SHALL run the same check and report its results.

#### Scenario: A module change causes a script error

- **WHEN** the new text of a module makes a selected page show a Lua error
- **THEN** the module is not written
- **AND** the output names the module and the selected page

#### Scenario: A template change alters visible text

- **WHEN** the new text of a template changes the visible text of a selected page without a script error
- **THEN** the dry run lists the page with the removed and added lines

#### Scenario: The selection covers every page type

- **WHEN** a template is used by 800 pages, and only one of them passes `kind=Aura`
- **THEN** the default selection includes that page

#### Scenario: A full check is requested

- **WHEN** the run asks for a full render check
- **THEN** every main-namespace page that uses the changed page is parsed

#### Scenario: No page uses the template yet

- **WHEN** no main-namespace page uses a template that the run would create
- **THEN** the render check reports that it had no page to parse

### Requirement: Data modules fit on a wiki page

`wiki generate-lua` SHALL fail when a generated data module is larger than the page size limit of the target wiki. It SHALL name the module and its size.

#### Scenario: A module exceeds the limit

- **WHEN** a generated data module holds 5.1 MB of text and the limit is 4 MiB
- **THEN** generation fails and names the module and its size

### Requirement: Every repository wiki file has a deploy path

Each file under `wiki/` SHALL be a page source that `wiki deploy-repo-pages` or `wiki deploy-interface` deploys, or a Scribunto `testcases` module that the local wiki stack runs. The repository SHALL hold no copy of a page that people own and no generated output under `wiki/`. A check SHALL fail and name each file without a deploy path.

#### Scenario: A copy of a people-owned page is added

- **WHEN** a commit adds `wiki/Raids.txt`
- **THEN** the check fails and names `wiki/Raids.txt`

#### Scenario: A deployed page source is added

- **WHEN** a commit adds `wiki/content/Category/Example.wiki`
- **THEN** the check passes, because `wiki deploy-repo-pages` deploys it as `Category:Example`

### Requirement: The data guide states which fields keep an editor's value

`Erenshor Wiki:Game data` SHALL list, for each template that generation writes, each field that keeps a value set by an editor when a refresh runs, and each field that merges such a value with the generated value. The list SHALL equal the preservation rules of the generator. A check SHALL fail when they differ and name the template and the field.

#### Scenario: A preservation rule changes without the guide

- **WHEN** generation starts to keep the Item field `description`, and the guide does not list it
- **THEN** the check fails and names `Item` and `description`

### Requirement: The data guide names the live game build

`Erenshor Wiki:Game data` SHALL show the game build id and its publish date of the live data modules. Its text SHALL read them from a generated data module, so a data deploy changes them without an edit of the guide.

#### Scenario: A new build is deployed

- **WHEN** the data modules of build 24405256 replace those of an older build
- **THEN** the guide shows build 24405256 without an edit to the guide's source
