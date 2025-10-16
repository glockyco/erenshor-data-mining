1.1. Agree

1.2. Agree

1.3.
Beware that we still have to be able to update legacy data in the wiki, so
we cannot focus ONLY on recent changes.

However, we MUST have some way forward
to do more targeted updates. For example based on recentchanges, but I've also
had several situations where I updated a wiki page, found some issues, and
wanted to re-update it again with the fixed content. Not easy to do currently.
If we "always" had info what the current state of the wiki is (based on wiki
fetches / recentchanges / pushes) that might resolve some of these pain points.

Also, a different pain point I noticed that there were pages that had some
error in the content which I couldn't fix right away in the auto-updates,
so I fixed the error manually in the wiki. However, with the next auto-update,
the manually fixed wiki page would be overwritten with the incorrect content
again (forcing me to manually update it again, etc.). Not sure how to best
deal with such situations. Any good suggestions?

Regarding the manual mapping: I'm afraid there's just no way around this.
We have quite a lot of legacy data in the wiki that we can't reasonably
migrate to use auto-generated mapping / conflict resolutions. So auto-generated
mappings are not really an option as far as I can see it. Do you dis-/agree?

1.4. 
Hmmm, I'm not sure where you're getting "maps JSON" from?
The maps use the SQLite DB for the data, as far as I remember.
Well, at least for everything except the tile configs (which, btw.,
is definitely something that we should automatically export metadata for
during TileScreenshotter use. - and screenshotting should be automated
at some point - and we should look into camera settings for the screenshotter
again to preserve some more of the visual effects of the game camera - and ...,
well I'm going a bit off-track here, all of this would be nice to have but is
not really the focus of the current refactoring / rewrite).

1.5. Agree

1.6. Agree

---

2.1.
Agree. The wiki is only one of the representations.
Not sure what you mean by "URLs configured, not hard-coded"?

2.2.
I think I prefer the monorepo with independent output modules.

Large repo size should not be too much of an issue because, all things
considered, the project is still reasonable small in scope (perhaps
somewhere around 10,000-20,000 LOC after the refactoring / rewrite,
I'd imagine, with a lot of that in simple data mapping code).

Mixed language tooling is something I'm sure we can deal with. And the
languages are still relatively cleanly separated, so that also helps.

Don't see much issue with dependency updates across languages. If anything,
keeping things in sync across fully independent projects is probably trickier
because it's more difficult to get the full picture.

2.3.
See above.

2.4.
Maps are actually at:
https://erenshor-maps.wowmuch1.workers.dev/ (Overview)
https://erenshor-maps.wowmuch1.workers.dev/Abyssal (one individual map)

How would the Shared URL Builder work across Python vs. TypeScript?
Also: please keep in mind that we HAVE TO consider resolution of name
conflicts for any wiki links. Just taking the "raw" item name would NOT
be good enough.

2.5.
Agree. A full task library is likely overkill / causes a lot of overhead with
only little if any benefit.

Beware that we HAVE TO be able to execute individual "stages" though.
But I'm assuming that will be discussed in the CLI sections(?).

Resume from failure sure would be a nice feature to have. For example,
I'd like to avoid having to re-run AssetRipper just because the sheets
upload failed for some reason. Of course, I could just manually execute
the sheets command instead of the triggering the full pipeline again,
but that's somewhat tedious, especially if the failure is in an earlier
stage and I then have to run multiple commands after each other to fully
finish the pipeline. Not sure how tricky it is to implement such a "resume
from failure" system though?

Parallelization of wiki / sheets / maps is not really all too relevant.
If I need to update everything all at once, I'd just open multiple terminal
windows and run one of the "deployment commands" in each of them. However,
in most cases, I'd still want to do manual checks for each deployment to
ensure nothing broke, so the limiting factor is not really processing time
but manual validation time anyway.

Not quite sure what you mean with "complex dependency graphs"?

---

3.
Just thought of something: how difficult would it be to generate CLI
docs automatically? Pretty much every time I worked with the CLI, it
was quite tedious because I couldn't remember all the commands so had
to step-by-step explore what's available, what the params are, etc.
If there was some "online"/browser-based single-page documentation
that of the full CLI surface, that might make things easier to find
via Ctrl+F? Maybe even more convenient than auto-complete (though
auto-complete in the terminal still would be quite nice to have)?

3.1.
Typer is fine.

The high-level structure seems reasonable as well.
We should probably discuss this in some more detail to figure out which
parameters are currently there, which ones are actually needed, which
commands / parameters would make for nice additions etc.

3.2.
Rich is fine. Bringing some more structure into our use of it to make it easier
to keep things consistent probably is a good idea. Any other suggestions here
(totally fine if not, I'm just curious)?

3.3.
TOML is fine I guess? Just curious about your justification to pick it over
YAML? For example, "Significant whitespace" is something that Python itself
also has, and "parsing inconsistencies" seems like quite a vague claim?
Compared to TOML's "flat" structure, YAML's indentations might actually
make it easire to a big-picture overview of "nested" settings / hierarchies. 

What would we need to switch to YAML? Would it be "worth it"?

Simplified config cascade is definitely needed. I'm somewhat hesitant about
keeping environment variables. What are the benefits of that over just the
two-layer config.local.toml + config.toml? Seems like that adds a lot of
potential for problems with, at best, marginal benefits?

Btw: not quite related but, should we think about dockerizing the project?
I think it would be nice to be able to just run things on a new system
without a lot of setup overhead but I'm not sure how realistic something
like this is with the unity dependency in our stack? Let's discuss that.

3.4.
Loguru seems interesting! Good opportunity to try something new!
We can discuss the exact retention / rotation settings later.

3.5.
Seems reasonable? Not sure about the exact settings for batches and
maxlag and delays etc. Can you please check what's good practice here?

3.6
YES! We're really lacking in terms of our test setup.
So many regressions that could have been avoided with proper regression
testing so known issues don't come back at a later date.

Please avoid overly heavy mocking. Advocates often go quite a bit overboard
with it, mocking every single thing. This certainly makes it easier to 
boost certain coverage metrics, but often introduces so much abstraction
that the tests are basically worthless.

Just to be clear: I'm NOT saying we should NEVER use mocking, but we should
really think about where it makes sense and where other testing solutions
would produce better results with less of a maintenance burden (mocks are
VERY costly to maintain, after all, especially in a project that still
keeps changing as much as our current one). For example: keeping a "library"
of wiki pages / snippets that caused issues in the past sure is a good idea
to avoid regressions even if those wiki pages don't exist in their problematic
form anymore.

I wouldn't worry about C# testing for now at all. Things "just work" there,
and we don't really plan to change anything about the C# code in the near to
medium-term future.

---

4.1.
Not sure the status and diff commands really add much benefit. Perhaps
that changes with our more robust core wiki implementation, but in the
current version, I'm pretty much only ever using the --dry-run flags
to see "required changes", though even that is quite lacking (but that
WILL hopefully improve with our better fetching logic).

What are you envisioning with "confirmation prompts"?

How do you plan to "resume after failures"?
Sounds nice as a bullet-point, but how should that work (UX/DX/implementation)?

4.2.
What do you imagine "edit summaries" to look like?
How to get the information for the edit summaries / how to build them?

How do we determine what needs upload and what is up-to-date?

What's the benefit of custom tooling for diff viewing over, e.g., using git?

Image upload automation is a MUST HAVE.

Not sure what you mean by "offline mode"? We SHOULD be able to perform
updates locally (so we can check them manually, if needed, before pushing)?
Am I misunderstanding you here?

4.3.
As mentioned at the beginning of this document, it's not really possible
to use an automated disambiguation strategy at the moment - at least not
for legacy content. We MUST preserve names of wiki pages as they currently
are. Even though a "refactoring" pass to use consistent naming strategies
would be nice to apply eventually, I'm afraid that's beyond the scope of
the current project refactoring. Not because it's particularly difficult
to implement, but because it's hard to update ALL existing wiki content
to use the new names without breaking anything.

However, perhaps we can use that system for future updates? Beware, though,
that disambiguated names MUST NOT conflict with any existing pages outside
of the ones we are covering with our entities. For example, if there
is a custom wiki page that has the name "uiae", then we still need to make
sure that we don't have a conflict with it even we have a new item "uiae"
that doesn't have conflicts with any of our other managed entity types.

Do you know what I mean? What do you think?

I think you have some of this considered already in your config suggestions
("overrides"), but please keep in mind that we're not only mapping page names,
but also display names, image names, and potentially other overrides down the
line.

4.4. 
I think in the current wiki, we're only using what you call
SINGLE_INFOBOX and MULTI_INFOBOX for multi-entity pages.

Well, maybe also COMPARISON_TABLE for the overview pages?
Not quite sure how you count those?

Tabbed infoboxes sure would be nice to have as an option.
Does wiki.gg support that?

Speaking of infoboxes: the wiki team has long wanted to introduce Cargo
to the wiki (the extension is available already), but we've only done some
very small-scale manual testing. How to properly integrate cargo?
Should that be considered in some way in our new architecture as well?

4.5.
We MUST NOT introduce any special markers into wiki pages. We MUST use only
the wiki normal wiki content. After all, this is a hobby project, and if
a new hobby comes along, the remaining wiki team (who are NOT contributors /
users of this project) must still be able to keep normal wiki maintenance /
operations going as usual.

So we MUST stick with our current approach of identifying what should be
changed or not using custom logic for different types of pages. Sorry,
but we can't put our own needs over the needs of the remaining wiki team.

4.6.
This is kinda related to the disambiguation discussion. But yes,
we need some way to track ALL conflicts, not just the ones for which
we have entities. As mentioned somewhere above, this MUST also include
random manually-created pages that have no association with our automated
wiki update system at all. From a UX perspective, how to best notify the
project user (i.e., me) of any conflicts that need to be resolved? The
current system is quite inadequate in this regard - you always have to
manually check via commands whether there are any conflicts, and the
conflict detection does not consider pages that aren't fully implemented
entities.

---

5.2.
Yeah, brittle stable keys are a big issue. We have some ID columns for
some types of entities (for example Spells have IDs even in the game files,
but we already observed cases of duplicate IDs, so those cannot be fully
trusted unfortunately). It's really a hard problem. If, e.g., a name changes,
we want to RENAME the wiki page so we don't lose any manually added content,
but how do we make sure we know which new page belongs to which old one?

What do you mean when you say "content-addressable keys"?
Content hash sounds nice, but which content can we hash for a key?
Similarly, which DB primary key can we use? As you can see from the
C# scripts, IDs are newly generated with every export (the DB is completely
cleared before writing data of a new export, basically). The current
stable key tried to address these issues, but really is a bandaid solution
that's trying to make the best of what we have. If you have better ideas,
please let me know. Either way: we should really rethink the registry from
scratch / do some brainstorming to see if we can come up with a better solution.

The registry is small, so I don't think lazy loading is really necessary.

5.3.
Ah! Here it is again! Good thinking with the 1. -> 2. -> 3. name resolution.

5.4.
I don't mind switching to SQLite. Not really a fan of the huge JSON file,
to be honest. Never even looked at it manually. Having it queryable might
make conflict detection easier? Especially if we also create some sort of
index of fetched wiki pages in the DB?

5.5.
Well, seems like you DID think of potential problems! Sorry for doubting you!
The main questions is just: which DB information IS stable across game
versions? I'm honestly not totally sure. Perhaps you can check this
and make some suggestions?

---

6.2.
As discussed, let's go with the merged monorepo solution.
Any tooling we should be aware of that might help us manage things?
Or are we better off just keeping things simple without any further
external dependencies given the project context / size?

You mention CI/CD, but we do NOT have any CI/CD.

6.3.
I guess there is some truth to the issues of full DB loading for maps.
However, we want to extend the maps in the future to also offer search
for items, characters, etc. so we can't really trim things down at all.
All data will be needed in some form eventually.
Any other solutions to deal with / avoid the long-ish loads?

6.4.
Seems reasonable? Is this what you suggested further up?

6.5.
Hmmm, there are some other ones, I think, that might be relevant?
The most prominent one is the "locally running full build" (whatever
that was called again). Like preview or something?

Other than that: seems reasonable.


7.2.
Not really very convenient having to set ERENSHOR_WIKI_BOT_USERNAME
and ERENSHOR_WIKI_BOT_PASSWORD in env vars IMO.

As discussed earlier, I'm somewhat on the fence about TOML vs. YAML.
Admittedly, I think TOML looks "cleaner", and we don't really have THAT
many config settings to get all too much benefit from YAML's nesting.

7.3.
Seems reasonable. Make sure that we have proper root directory detection
and we're probably good to go. Anything else that might cause issues down
the line?

7.4.
Seems ok. Would be nice if we didn't need libraries, but it's really only
a minor inconvenience compared to some other config formats.

7.5.
As discussed, I'm not really a fan of environment variables.
Why's that "better" than, e.g., .env? Or the config.local.toml?

---

8.1.
I'd really rather do the Big Bang Rewrite. As you might know from the 
CLAUDE.md, I'm not a huge fan of keeping legacy code around. If we go
for the move, we should do it properly. Everything else is just a maintenance
nightmare with yet another half-finished solution to keep going.

8.3.
Yeah, we still need to have the old system available in some form to
be able to do the comparison tests. But the two systems should really be
clearly separated. NO shared code at all. Just move the old system to some
legacy / backup folder and start the new architecture from scratch.

8.4.
Just NO. As discussed, that's just a maintenance nightmare. Clearly separate
the two systems (old vs. new). NO shared files. NO shared code paths.

8.5.
Too much effort. Clear cut!

---

9.1.
Yeah, by far the most important thing right now is the wiki page generation.
That's what keeps causing issues, not necessarily just because of "errors" on
our side, but because we are missing special casing from the wiki that we
simply have not implemented yet. As we are progressing with the auto-update
implementations, we MUST make sure to add proper tests for them to avoid
regressions. Many of those are probably implicitly encoded in export logic
already, but are not explicitly validated due to our sub-optimal testing
practices so far.

9.2.
Beware that constructing a test DB is hard work and often produces cases
that don't quite match real-world scenarios due to some subtle differences.
An option might be to just copy the current, most recent DB and use that
for implementation of integration tests going forward. We can still update
things as needed over time.

What do you think? Is this proper testing practice? Or should be go with
a different solution?

9.3.
Seems good enough. Just need to make sure the mocks match the actual behavior.
Perhaps we can extract / rebuild / log some "real" responses and "replay"
them for some test scenarios.

9.4.
Don't test C# code for now.

9.5.
Slippery slope with the exclusions and subset runs.
How do we make sure that longer-running tests are not just ignored?
Developers (and LLMs) like to take the easy way out if they feel the
clean solution is "not worth it" / "too much effort".

---

10.
Yeah, backing up config is propably a good idea.
I know there is some experiment tracking tooling for, e.g., ML experiments.
I assume that's overkill for our purposes?

Beware: it's not (our) "editor scripts" we want to backup (they are in the
git repo anyway), it's the actual game scripts in the Unity project.
Do you think it's best to zip them up? How would we go about (manually)
diffing them to figure out what has changed across game versions?

Which reminds we: I think I mentioned that we want to have some way to
be automatically "notified" of "relevant" changes between game versions
that need some sort of manual intervention. How will that work? I don't
think I've yet read any plans for that?

Beware that game versions / build numbers look quite different from what
you show in the examples. Don't think that really changes anything about
the plan, but though I should point it out.

As discussed, I'd like to keep ALL backups (i.e., 1 for every build / version 
of the game that we ever ran through our pipeline). No need for any retention
policies or anything like that. If the data ever becomes too much, I'll
just delete some stuff manually.

Perhaps some sort of info might be nice after a run that shows how many
backups we already have, how much space that takes up on disk etc., just
to make sure we don't lose track of it?

Btw, that's a general thing that would be great to have in CLI commands:
getting relevant (meta) information as command outputs. Like which command
to execute next to continue the processing pipeline, or where to find logs
that will be / were produced by the execution of a command. Probably tricky
to enforce throughout the whole project. Any core logic we can add for that
to make this easier / get it "for free" for all commands?

10.5. Agree. Go with local backups.

---

11.
Ah! There is the change detection system! Sorry for being impatient earlier. ;)

New mechanics CAN be visible in ScriptableObejcts, but often also come
from completely new C# scripts.

Not sure what you mean by "schema changes". The game does NOT have a DB.
We DO have one, of course, but we know about any changes to DB anyway
because we're the ones who need to implement them....

Should probably discuss this a bit more to figure out what are actionable
insights that actually help (wiki) maintenance and what's just random noise
that doesn't really help anyone.

We're not using CI/CD currently, and don't really have any near-term plans
to add support for it either.

---

12.1.
I'm quite hesitant about "smart suggestions". They probably add a lot of
maintenance overhead? Unless there are some pre-build systems for that?

Completion srcipts sure would be nice, IFF they are easy to create (ideally
automatically).

As mentioned somewhere earlier, some "online" / browser-based documentation
might be a nice addition as well. Any way to automate this?

12.2.
YES! Standadization would SO NICE!

12.3.
YES! As discussed, getting hints about next steps is such a QOL add.

12.4.
Still need to discuss what exactly we want to log, but YES: we definitely
need better log discoverability, e.g., through output info that points to
the logs.

Quick log access commands sound nice. What do you envision should be 
shown by them? I'm still a bit unclear about the specifics?

12.5.
Oh, didn't even think of that. But yeah, good error messages are always
appreciated of course!

12.6.
Yeah, would be nice to see what commands can/will do.
Even if not much info can be provided, getting just a very rough idea is
already worth a lot. 

12.7.
Hmmmm, shouldn't we be consistent with the validation commands as well then?
Like, call them all "... ... doctor", for example? What do you think?

12.8.
Sounds reasonable. Question is: how do we ensure we don't have a lot of
duplication across dry-run vs. interactive mode and keep things actually
maintainable with reasonable effort?

Not sure what you mean with "batch operations"?
For this specific example, as mention further above, we don't need any
command at all because backup management will be done largely manually.

---

13.1.
I think we do NOT need a task library.

13.2.
That's what the mappings are for? If multiple entities map to the same page
(via explicit, manual mapping - otherwise it's a name conflict), it's a
multi-entity page. Simple as that. Any issues you foresee with this?

13.3.
As discussed earlier, the maps really need the full DB. So JSON is not
a solution. Any way we can improve on the download size issue?

13.4.
As discussed earlier, I'd prefer SQLite storage for the registry.
It's still very much editable, albeit with tooling.

13.5.
Hmmm, interesting point about a separate JSON file for C#.
But I think the single-source-of-truth solution with TOML will
cause fewer issues down the line. Having an additional dependency
really isn't all that bad, all things considered.

13.6.
Yeah, that's not really relevant now. We'll worry about it when we get
there. But it'll most likely just use the SQLite DB as well.

13.7.
As mentioned: no automated testing for C# scripts please.

13.8.
There needs to be some path to full automation. We're probably not quite
stable / reliable enough with the name conflict resolution, so semi-automatic
is the way to go. However, eventually, the uploads should be fully automatic.

13.9.
Yeah, good enough. No need to overthink this. If we correctly handle wiki
responses about rate limits, the exact delay values shouldn't matter too much
as we "simply" adjust dynamically to what the wiki tells us to do.

13.10.
I don't foresee any further variants. You never know, of course, but I
wouldn't worry too much about it for now. If we can support 3, it's probably
not too hard to extend things to 4 if we really have to at some point.

13.11. 
How exactly do you envision type sharing via JSON schema?

13.12.
As mentioned, would be nice to have CLI docs. Other than that:
I think it's too early for full documentation of the project.
With how fast things are changing (see, e.g., this rewrite plan...)
having to keep docs updated just adds huge amounts of maintenance overhead
with questionable benefit (better to have no documentation than documentation
that is wrong).

13.13.
All good ideas, but I'd probably not tackle them right now.
We have more pressing things to worry about.
Anything we can / should do to make dockerization easier down the line?

13.14.
CLI output only please.

13.15.
Well, some tracking probably wouldn't hurt?
If we introduce a new SQLite DB anyway for mapping / registry info,
we might as well use it to store some run metrics? 
What do you think?
