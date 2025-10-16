Architecture:

1.2:
Not sure we will need src/erenshor/outputs/maps.
After all, maps will directly access DB data.
But feel free to keep it in there for now.
Still have to think about how to properly get the
DB files into the static assets of the maps subproject.
We don't really want to move it out of the variants
directory, but we still need it on Cloudflare as a
static asset.

1.3
You're missing the:
`erenshor maps dev` command now.
dev and preview are different things in npm (or Svelte? not sure which one provides it...), aren't they?

We seem to be missing commands for test execution?

1.8
Beware that we also have tests for the maps project.
Don't forget about them.

1.9
The C# project has some other dependencies as well,
but doesn't really change anything about the architecture.

2.1.
Yeah, please check which ones we already support.
For example, items have quite a few "subtypes",
some of which use their own specialized templates
rather than the general item template
(e.g., weapons, armor).
Also: spells and skills share an ability template.

Should also plan ahead which templates we need to support
in the future (e.g., quests).

Please check all of this.

---

Task 1:
I already told you that I will NOT provide DB backups.
YOU should make suggestions for stable IDs that we can discuss.

Task 2:
Yup, please review. Your current template inventory example
has quite a few inaccuracies.

Don't worry too much about plain text sections.
Those should be a backlog task.
We just need to make sure the new system
is flexible enough to support adding them.

Task 3:
Yup, please research.
Make sure to take best practices into account.
Cargo is a MUST HAVE. Option C is NOT valid.
We should try to make things as simple for
wiki maintainers as possible, even ones that
don't have access to the automation that comes
with this project. Wiki maintainability is an important
factor.

Your implementation plan is quite strange. I AM the
representative of the wiki team. So no need to wait
for long feedback cycles. We should just design a
clean Cargo architecture upfront. Can always adapt
things later if we need to, but the system should
work for everything (items (weapon, armor, ...),
characters (friendly, non-friendly), abilities
(skills, spells), quests, ...).

We CAN leave this as a backlog item with high priority
if you are sure that adding cargo later will not
cause any additional (rewrite) overhead compared
to integrating it right away.

Task 4:
Yup, please research.

Task 5:
Eh, let's put performance metrics on the backlog for now.

Task 6:
Let's put log commands on the backlog for now.
We can just manually access logs, that's good enough
for a first throw. Definitely have to include the
"logs at ..." messages to command outputs though
to keep log discovery easy.

Task 7:
Eh, I'm not convinced generation from schema is a
good idea. Let's put this on the backlog. Just create
the python + typescript models manually (as needed).

---

Thanks for the current feature list.
Keep in mind though: not everything we have current
is supposed to stay. We want to IMPROVE things, after
all - and part of improving things is removing what's
bad or useless. That's why we're putting in so much
effort now to redesign the major system of the project.
We want a clean cut. Don't hang on to legacy baggage
that is bad for the future of the project.

You've got this right in the validation criteria,
but I wanted to repeat it again, because it really
is important that we focus on things that actually
improve the project and remove things that make the
project worse.

