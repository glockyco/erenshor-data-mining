## Fundamentals

Erenshor is the game.

The project is a single-dev hobby-project that does data mining on Erenshor
to produce data for the wiki, Google Sheets, and interactive maps.

The interactive maps project is currently at:
/Users/joaichberger/Projects/erenshor-maps
However, like the wiki project was merged in commit:
bdf8afb0087ced885fa93d5a82575f8d0457d1b1
the maps project should also be merge into this one eventually
(ideally / maybe with this refactoring / rewrite pass?).

So there really are 3 target representations for the data:
- wiki
- sheets
- maps

It is critical that we are aware of this. All three representations
must share the same underlying data source (i.e., the data in the created
SQLite database).

So we have game downloading + extraction + exporting as precondition for
all three target representations, but NO direct dependencies between the
target representations. However, there should be interlinking between the
wiki / sheets / maps. For example, the sheets link to the map for location-
specific data (e.g., spawn points, treasure locations, secret passages, ...).

In the future, we want to add a fourth "representation":
an in-game compendium of game data implemented as a bepinex-based mod,
loosely inspired by, e.g., WoW's "Adventure Guide",
intended to be used like an "in-game wiki", as a quest guide,
or for completion tracking (with no-spoiler, low-spoiler,
and full-spoiler mode that provide different amounts of information
for obtained / seen vs. unobtained / seen items, quests, NPCs, etc.).

---

## Data Extraction

Consists of:
- steamcmd-based game download
- assertripper-based unity project extraction
- editor script-based data extraction via unity's batch mode

The output is a SQLite database with all extracted game data,
ready for use by the following independent processing steps that
produce the target representations (wiki, sheets, maps, etc.).

---

## Multi-Variant Support

---

## Wiki

Needs to use existing wiki pages as a starting point to
be able to preserve manually added information that's beyond
just purely "hard data" from the game files.

-> fetch wiki pages
-> update locally
-> push to wiki

Needs to also support image uploads.

We really need to rethink though which features are actually
necessary to enable this wiki maintenance.

For example, local diffing sounds nice at first, but it doesn't
seem to provide any really actionable information - at least that's
the impression I got from working with the system recently.

What's actually required / beneficial, and what's just unnecessary fluff
that increases maintenance overhead and failure surface, but doesn't
meaningfully help with wiki maintenance in day-to-day operations?

Either way, we need to rethink the details of our wiki approach
from the ground up.

For example, how to properly do
automated wiki updates from extracted data, making sure to include
features / requirements such as rate limiting as first-class citizens
that are at the core of all interactions with the online wiki? How
can we keep the API requests to a minimum to avoid even running into
such situations wherever possible? And similar issues that might
not be obvious at a cursory glance but can quickly dominate discussion
if not done "the right way". For example, we definitely MUST include
the update log (not sure what it's called?) of the wiki to avoid
unnecessary re-fetches, re-uploads, etc. of unchanged data. There is
no way around this. Downloading / Uploading everything on every wiki
interaction is not a viable way forward, and definitely is not proper
wiki / API etiquette. Our current solution for this is very amateur-ish
and really has a lot of pain points that are not properly resolved.
Doing this properly will probably (hopefully) obviate some of our
current wiki constraints through a more robust and better thought-through
core wiki update architecture.

The other big challenge is disambiguation (i.e., what the current mapping /
link registry system is trying to solve). The whole system seems somewhat
brittle and error prone. Can we do better by rethinking things from scratch?

Another think the we HAVE to support is everywhere at some point is
multi-entity pages. We already have this for some (e.g., spells, skills)
but don't for others (e.g., characters).

We are also still missing support for many other entities, e.g.,
quests, zones, factions, etc. While those don't have to all be implemented
in the refactoring / rewrite right away, the architecture needs to be 
built with those (and other extensions) in mind. For example, which "features"
need to be implemented in a generalized form so we don't run into duplication
down the line? Which information is required right now about these entities
to create correct wiki data (e.g., name conflict resolution even if no
full page updates are implemented yet for a specific entity type.)

Also, not everything is an infobox or a simple table.
We need to think about ways forward if we ever want to add content
outside these clearly defined boundaries. For example, character dialogs
are currently shown in the main text of character wiki pages, with some
headings etc. to categorize the situations in which they occur.
We don't have to have a solution for this right away, but the update
system MUST be flexible enough to support such use cases in the future.

What else have we missed in our "naive" first shot at automated wiki
maintenance tooling? What issues might come up in the future that we 
have just not encountered yet? How can we plan for them now without
overengineering (-> YAGNI)?

P.S.: the old wiki project was already merged into this one,
so there's no need for any "database copy" into the wiki project
anymore, even though that might still be implemented somewhere.

---

## Sheets

---

No comments here for now.

---

## Interactive Maps

How to integrate the maps project into this project?
It's a TypeScript / Svelte project and hosted on Cloudflare. 
How to make sure links from sheets to maps are always up to date?

---

## Compendium (Mod)

TBD (make sure to plan for it, but no need to discuss any details right now)

---

## Logging

Should rethink whether our current logging system still matches our
requirements. We primarily use logs for debugging. We want logs to be
easily discoverable. We probably don't need to preserve logs for long
periods of time. Anything from older versions of the projects is likely
dead weight that won't help anyway.

What libraries are there to help with proper log management,
keeping in mind that our demands are quite modest (the project
is used by a single dev, so we don't have any need for large-scale
log storage, heavy parallel use, automated log analysis, etc.).

---

## Backups

We want backups of C# scripts from the unity project and of the
created SQLite DBs. One backup of each per build / version of the game.
Since neither C# scripts nor SQLite DBs change within a single 
game build, we don't need to keep multiple per build. If we change
the logic that creates the DB, outputs CAN change, so we need to
preserve the most recent DB for the build.

Backups should be "tagged" by build / version (for unique identification)
and by date (for easier discovery / search).

Anything else important we're missing?

---

### CLI

ALL functionality must be accessible through the CLI.
ALL functionality must be discoverable through the CLI.
CLI commands should be as user-friendly as possible (progress reporting,
completions, suggested next steps, clean output with details in logs,
clear info where logs are stored when running a command, ...).
CLI commands MUST NOT be overloaded with loads of unnecessary parameters.

The most critical issue we're currently having regarding CLI is that
we have 3+ different CLI implementations split across shell scripts
and Python. We MUST move everything to python, and we MUST rethink
the structure of the CLI from scratch, taking a critical look at
how we can do better and learn from our mistakes.

What else is required for good CLI design? What libraries are there
to help with this?

---

## Pipeline Architecture

Are there any libraries we should use?
Or is this overkill for our use case?

---

## Entity Types and Relationships

These are really constantly changing as the game evolves.
Ideally, we should have a system in place that notifies us of
relevant changes so we can properly account for them throughout the whole
processing pipeline.

Similar thing for any other new game data and scripts:
how can we make sure we don't miss any important changes / additions
beyond what is dealt with by automated "data updates" (e.g., new game
mechanics, new game content that can't be properly accounted for full
automatically but needs some manual intervention to, e.g., describe
correctly in the wiki, etc.)?

---

## Configuration

We need one unified configuration system that should apply across ALL
components of the project. Since it's a multi-language project (C# for
editor scripts and (in the future) companion mod, python for most processing,
TypeScript for maps) we HAVE TO store configuration settings in a
language-agnostic format that's easy to process and work with across
all of our use cases. Full cleanup of everything that's not necessary
(e.g., endless fallback logic across uncountable different overrides - yes
some overrides ARE necessary (e.g., global vs. local/test settings), but
we don't need a 10 layer cascade => YAGNI, KISS).

Path resolution is a key part, and needs to be built for multi-variant
support from the ground up. There should be no way to do things wrong here.
We need to ensure that it's obvious how to do things the right way. Issues due
to improper use of variant-specific paths have caused so many issues already.

---

## Data Source Transformation

How many different INTERNAL representations of data do we really need?
What's the minimum that we can reasonably get away with? Every addition
representation adds additional overhead and failure points.

There's no way around the external representations (game, wiki, sheets, maps,
mods, etc.), but we should try HARD to avoid unnecessary bloat from that causes
significant maintenance overhead in our internal code. Having 5 different
internal representations of an item is certainly NOT the goal.
