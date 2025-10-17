Agree on the compliance feedback.

Please don't use any TYPE_CHECKING guards.
Other than that, agree with the quality feedback as well.

Agree with the testing feedback.
Will have to take a look at integration tests and
E2E tests as well at some point, but I think we're still
too early in the rewrite to really get much benefit from
that. Too many components are still missing to properly
test their interactions.

Why do we have an .env file? Didn't we say NOT to use
.env for configuration? Those should be in the 
config.local.toml file, shouldn't they? Is this just
a leftover from the legacy implementation?
No need to revoke the password - it's gitignored so
never got outside this machine.

Google credentials should probably be moved to 
config.local.toml as well? As well as the spreadsheet
IDs (as mentioned by the review)?

Yeah, some disk space protection (-> warnings)
probably would be a good idea.

No need to worry about file/directory permissions.

Don't add any security docs or README yet, please.
Things are still changing so fast, it's just a nightmare
having to keep everything in sync. Better to have no
documentation than incorrect documentation.

Don't worry about log sanitization.
gitleaks looks nice though! Installed right away!
Please add to our pre-commit hooks.

No need for a secrets-manager.
We're still just a one-person hobby project.
A full-blown secrets manager seems overkill.

Also: please stick to the plan for map merging.
It's task 22 for a reason. No need to tackle it right away
since we still have earlier tasks to work on.
