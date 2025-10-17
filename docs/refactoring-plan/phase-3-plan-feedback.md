## Analysis Feedback (New, v2)

We might have to preserve some more of the item templates later.
They automatically add "tags" such as [[Category:Molds]] to the pages.
I suppose we can add those tags automatically instead? What do you think?
After all, having that encoded in the template prevents variation across
items in a category (e.g., multi-category tags). Hmmm, yeah, I suppose
going the "{{Item ...}} with separate [[Category:...]] tags" route might
be the better choice. Do you dis-/agree?

I'm not sure it's a good idea to have all the precondition checks in a single
file. That's bound to blow up over time A LOT! Probably should introduce some
more structure / architecture to it. How can me make sure we don't easily
forget to add some precondition checks? And how to make sure we don't forget
to use the precondition system? Seems quite easy (too easy) to unintentionally
circumvent the system in the future. Quite a lot of "boilerplate" to add to
each command as well.

Regarding legacy template replacements: please check which ones we already
had in the old code as well. I know that you missed at least Character -> Enemy
in the examples you showed.

Please don't overcomplicate the field preservation system.
What are the essentials that we really need?
Seems like override is default anyway (or at least sohuld be).
And everything else can be handled by "custom" handlers.
So even "preserve" should just use a custom handler instead (but one that we
already implement in the first version of the system).
Please check the old code what's actually used.
And I'm pretty sure we need to make these things template-specific in some way,
or at least have the option for it.
Please rethink the system based on this feedback.

Does the manual edit notification workflow have good UX/DX?
Anything that we could do even better to make cases easy to discover
and review without further increasing the CLI surface? We already have
quite a lot of CLI commands, so anything that explicitly requires manual
use of these commands ("pull") is quite easy to forget compared to things
that are automatically shown in the output when appropriate ("push").
Really need to get the structure of the outputs right though - as more
things get "pushed" automatically, it becomes easier to overlook things
as well, especially if certain sections are very long. How to ensure
discoverability without overloading the user?

## Analysis Feedback (Old, v1)

Following our "fail fast" principle, we should abort any pipeline runs
if any of the critical export steps failed. To ensure that separate
individual command execution behaves properly, we should also add checks
to each command that run BEFORE the actual command logic and check whether
all necessary data / files / etc. is available (similar to our doctor commands,
or perhaps we can even reuse them? not sure, please think about this). Either
way, there should NOT be any partial backups - instead, the command shuold
FAIL fast and loud before performing any potentially destructive operations
if it some requirements / preconditions for successful operation are not satisfied.

Also: is it really useful to zip the backups? We want them primarily to
run different types of diffs (e.g., compare DB data to older game versions,
compare source code of scripts to identify new functionality, etc.). Is tihs
still easy to do if the files are zipped up? We do NOT need any restoration
from backups. After all, the game will never revert, and if it does, we can
just recreate everything from the "new" / "old" verison anyway. So backups
really are just a feature for identifying changes across versions (we still
need to work on this more in the future, but that's another topic...).

I don't think we're still using all the (item) templates that you mentioned.
At the very least, we decided to discontinue Consumable templates and use
the basic Item templates for those instead. Not sure about molds and ability
books. Also, Weapon and Armor ONLY use the Fancy-Weapon and Fancy-Armor
templates - the non-stat-related info (drop location, vendors, ...) use the
basic {{Item ...}} template. You should be able to figure this out from the
old scripts. Please don't make assumptions purely based on which templates
exist - as mentioned, several of them are legacy ones that should NOT be used
anymore, and should not be preserved in the rewritten page handling logic.
However, we MUST be able to REMOVE such templates from existing wiki pages
(e.g., replace {{Consumable ...}} with {{Item ...}}). Can also find some of
this logic in the old implementation. Also, please beware that, e.g., Weapon
and Armor pages use multiple templates on the same page (one {{Item ...}}
and three {{Fancy-Weapon ...}} / {{Fancy-Armor ...}} each). Definitely
a VERY good idea to have some reusable components though that can be
included (stats, drops etc.)! I agree that inheritance would overcomplicate
things (-> "favor composition over inheritance"!).

I don't think "vandalism detection" is something we can reliably do. This
is just feature creep that would blow up our implementation WAY too much.
I think we MUST use manual configuration here that defines which fields
should be preserved. For pretty much any field, I can think of a valid reason
why certain automated detection logic would NOT work. Not sure how to deal
with merges though, to be honest. Probably best to just keep the old value
then until we have our update logic well enough implemented that we can
confidently replace those values (i.e., no merging, only replacements when
we are confident about them). Or perhaps some way to define custom resolution
strategies that can be set for individual template fields. Kinda like that
ideal actually. Can you design a (simple) system for that? I don't think
reacting to recentchanges will get us any useful solution. Too much effort,
too many things that can go wrong. And we want full automation, which is
not really feasible with a system that is so brittle. Focus on the essentials.
Manually defined preservations (+ optional custom field-based resolutions)
seem like a reasonable approach that doesn't blow up complexity too much.
If we can get notified of manual edits anywhere on the page, that would still
be great though -> allows us to list pages that might need manual intervention /
validation after the update has finished (ideally: locally, so we can handle
things before they go live).

Regarding you questions:

Q1: We should keep backups indefinitely. However, make sure to clearly
show how much space is taken up by backups whenever a new one is created.
That we, we don't lose track of it (-> UX/DX focus!).

Q2: See my answer / request above.

Q3: No vandalism detection please. We cannot do this with reasonable effort,
and the wiki hasn't really seen any vandalism at all anyway.

Q4: Eh, how would you detect this? We can't do cheks on upload, because
fetching individual page contents for each pushed page consumes to many
API requests (-> rate limiting). And in the final implementation, the
fetch -> update -> push process shouldn't take very long anyway. So I guess
we just overwrite whatever is there?

---

## Plan Feedback (Old)

Please think hard about the backup system again.
I don't think the current plan matches what we discussed during our
earlier planning sessions + discussions.
As far as I remember, we want 1 update per game build.
NOT 1 DB backup per "DB version" (we don't have a concept of DB
versions in part of the project)! If we run extraction / export,
multiple times on the same game version, old backups for this game
build / version should simply be overwritten (DB, scripts, configs). If
we have a new game build / version, we create a separate backup that
does not overwrite the older ones for earlier builds / versions.
Just to be clear: we backup DB, game scripts (C# files of the GAME,
but NOT our editor scripts), and configs. At least that was the plan.
Backups should be created automatically when doing extraction / export
(whatever we're calling it now - the step(s) where we're getting the data into the DB).
Understood? Do you dis-/agree?

Beware that we have many different item pages, all of which need different
templates and different generation code. You can look at the old implmentation
to see what we already had earlier, and at recent planning documents to see
which ones we still need to add in the future (some new item types, but also,
e.g., quests). Probably a good idea to take a look at the old implementation
to figure out which special cases we might have to handle. But PLEASE do NOT
just copy the old logic / architecture 1:1 - we're doing the rewrite becaause
we want to do BETTER than the old implementation. 

Regarding template data replacements: beware that we need to have some
special logic for preserving certain manually-set values. You check in the
old implementation which fields were affected by this, but really, we should
have a more robust / reusable system at the core of the page update logic
for this. This should not require manual intervention. However, would be
interesting to see if we can use recentchanges to identify manual overrides
automatically for ANY template fields. Not quite sure how that should work
though - probably not feasible / ideal to preserve ALL manual changes, because
some might be wrong, or outdated due to new game versions etc.
Please think about this some more (happy path, potential edge cases and
interactions, how to deal with with this (UX/DX), ...).

Please also think thoroughly about the UX/DX for conflict detection and
resolution. I think we've discussed this a bit in earlier planning sessions,
but we should really thank about it some more to make sure we've got all
things covered.

We move docs to the backlog. Perhaps we want to tackle some other backlog
tasks before that. We'll think about that later.


---
