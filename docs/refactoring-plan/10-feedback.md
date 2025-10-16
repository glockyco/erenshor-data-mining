
Regarding your questions:

Q1.1: Please check out the current implementation.
Q1.2: We're currently updating infoboxs and tables. Future plans also include plain text sections. So we need to be able to support both in the future (though not right away).
Q1.3: I'm afraid changes of some columns are quite rare. What do you think should be stable columns?
Q1.4: There aren't any prefix disambiguations. Only postfix disambiguations. E.g., "... (Item)", "... (Spell)", "... (Skill)" etc., "... (Quest)" etc.
Q1.5: Let's leave the diff command for later. Put it on some backlog or something.
Q1.6: If the flag is used, we should resume. If it's not used, we should not resume. No need for any timeouts.

Q2.1: As early as possible. extract and fetch seem reasonable. Manual is not good enough - it's easy to forget (but might be useful as a separate command anyway to do on-demand checks in addition to automated ones).
Q2.2: Yes, if there is no conflict, just use the appropriate "name" (Items.ItemName, Spells.SpellName, ...).
Q2.3: Only resume if we provide the flag. But make sure to suggest the "flagged" command on failures -> discoverability / UX / DX.
Q2.4: Tough one. How do we handle, e.g., wiki push if it is interrupted? Do we store enough state anyway that this will not cause unnecessary updates when the command is called again?
Q2.5: Add to the backlog item for diff implementation. We'll think about this some other time.
Q2.6: Let's worry about maps improvements some other time. Let's put it on the backlog.
Q2.7: Another one for the backlog.
Q2.8: Just keep it simple for now. Just a clear, concise list of commands, parameters, etc.
Q2.9: I think Markdown is the better choice for our use case.
Q2.10: Keep it simple.
Q2.11: Realistically? Not at all. But it would be nice to have if we ever have to hand over the project (hobby projects rarely last forever, but the wiki will need maintainers for quite a while). Let's put docker on the backlog for now.
Q2.12: Tool installation and configuration (paths etc.) is probably the biggest one. So if we do docker, we HAVE to include Unity as well. Either way: Docker is on the backlog for now.
Q2.13: Nah, not interested in dev containers.
Q2.14: What do you think is a good / "best-practice" solution here?
Q2.15: Just on manually / on demand is good enough.
Q2.16: Nothing off the top of my head. Just make sure we track them as we encounter new ones. You can check the implementation to see if you can figure out any old ones.

Q3.1: Well, since every auto-update overwrites any manual fixes, they are VERY common right now. Every auto-update needs to be babysit by a wiki maintainer to fix any "incorrect" overwrites. Very annoying. Very time-consuming. Destroys trust in the auto-updates.
Q3.2: Yeah, finding which images need upload / have changed is a big one. Will hopefully get better with the "recentchanges" so we can check if any changes in-game are newer than the most recent upload (e.g., spells / skills sometimes have their icons changed for various reasons). Bulk uploading already works (see the current implementation). Naming and organizing as well (again: see the current implementation).
Q3.3: Let's keep it semi-automatic for now. But the ultimate goal should be full automation.
Q3.4: WARNING is probably the most appropriate.
Q3.5: Any good suggestions here? What do you think will be the use case for the command? Do we need it?
Q3.6: Again: what do you think would be useful? In which situations do you think this command will be used?
Q3.7: Backlog.
Q3.8: Nah, those estimates are bound to be inaccurate. No need to have them.
Q3.9: Please don't overcomplicate things. Ideally, it should show exactly what would happen (=> same progress outputs as non-dry-run command). In practice, that might not always be possible, but that's what we should strive for.
Q3.10: Eh, let's leave confirmation prompts out for now. We have dry-run mode.
Q3.11: What do you main "might feel odd"? Any specific concerns?
Q3.12: "How should we implement type sharing via JSON Schema?" That's what I was asking YOU! It was YOUR suggestion to use JSON schema. So, how would you go about that? Any tooling support? Is it worth it?
Q3.13: Documentation (except for the auto-generated CLI docs) Doesn't matter right now. Put it on the backlog.
Q3.14: Use SQL. Whatever metrics you think might be useful / interesting to have. What's actionable?
Q3.15: Verbose looks nice I think? Keep in mind: most commands will be used quite infrequently by me, so it's useful to have some useful hints.

You didn't answer my question about using Cargo in the wiki at all.

We really don't need any timeline estimates. Remember: this is a solo dev hobby project. We'll get it done whenever we have time for it.

Regarding your risks and mitigations:
Risk 1: that's kind of a dangerous statement to make. We WANT to change some things. Some old things are not great. Some new things are necessary. That's part of what this refactoring / rewrite is about.
Risk 2: Yes, asking for help is important. We still have the old implementation, so there's always a safety net that we can fall back on. However, I really think our planned improvements will do much good.
Risk 3: Yup. Thorough (comparison) testing is the name of the game.
Risk 4: Yes. We definitely need to do a check for any missing functionality before we get started. Please add that to the plan.
Risk 5: We'll manage. I'm certainly hyped. ;)

Major decisions:

- Yup, big bang is good.
- Monorepo is good.
- Python-only CLI is good.
- Two-layer config is good.
- SQLite is good. Keep as-is for now. Improvement ideas -> Backlog.
- Requested analysis from you regarding stable names for all entities (including ones we haven't fully implemented yet, such as zones, quests, etc.).
- Keeping all backups is good.
- Testing python and skipping C# for now is good.
- TOML is good.

6.1:
- What about the "preview" command I requested for maps?
- Somewhat hesitant about the --quiet / --verbose flags. Sounds like a lot of implementation effort? We're logging anyway, right?

About critical issues:
1: Yup, manual content preservation is importand - and it's tricky. Should support at least infobox and table updates. Later on also main text updates (and perhaps others). Would be nice to have pre-defined section structures for different page type eventually, but I think we'll have to put that on the backlog for now. Of course, if we can do some pre-work to make that easier in the future, I'm more than happy to do so. 
2: Backlog.
3: As discussed. Please research potentially stable IDs / Keys.
4: Yup, conflict detection is important. Please refine. Current analysis looks good, though I'm still somewhat hesitant about the cost-vs-benefit proposition of automated resolutions. We need to check them manually anyway.
5: Should this checkpointing / state tracking be in the DB? Good thinking with the edge cases!
6: Backlog. But some good ideas in there. Like the reporting.
7: Thanks! TOML it is then.
8: Introspection seems ok I guess. As discussed: please just generate markdown. Don't have CI/CD and don't plan on adding it. Per-commit hook seems somewhat expensive (but might be the best stop-gap solution for now - in addition to manual triggers)?
9: Backlog.
10: Not sure about the Git vs. non-Git storage. What's best practice?

