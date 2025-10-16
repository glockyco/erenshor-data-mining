Cargo:
Put into backlog for now.
The future effort is the same as the current
one (wiki update overhead is irrelevant, that's
what we have auto updates for), but deferring
Cargo for now avoids huge manual validation
requirements beyond what we already need to do
as part of the refactoring / rewrite.

Stable IDs:
Can't really use ID columns. Even though they
come from ScriptableObject ID fields, they are
NOT always guaranteed to be unique. We've already
had cases of duplicate IDs. So we'll have to go
with resource names etc. - basically leave things
as they are in the current implementation, right?
And then add the new ones for quests + factions.

Templates:

Current templates seem about right.
Beware that the fishing stuff is currently broken
I think. Not sure why auras are doing their own
thing - they should be an item "subtype".

Agree with the high-priority new templates.
Don't think we need templates for classes, mining
nodes, achievements, teleports, doors, and books.

Crafting recipes are handled by the Molds
template. Molds ARE basically crafting recipes.

Please avoid template inheritance shenanigangs.
Just keep things simple. Those are not files
we are touching / modifying on a regular basis,
so readability trumps maintainability.

Fixtures:
I'll trust your recommendations.

---

Your questions:

Q1:
Move cargo to backlock (high priority after 
the current refactoring / rewrite).

Q2:
Hybrid seems fine.

Q3:
Maps optimization is backlog.

Q4:
Shell completion is backlog.

Q5:
Defer is fine.

---

Regarding next steps:

Cargo is backlog.
DB hybrid approach is confirmed.

Feature checklist: please stick to our new plan.
I don't think we missed anything critical. Things
that we didn't explicitly discuss the scope of
can most likely just stay as they are (e.g.,
C# listiners, AssetRipper stuff, ...). Of course,
don't just copy things blindly 1:1 - make sure to
implement any necessary changes to fit things to
the new architecture (as needed).

Q3-Q5 as answered above.
