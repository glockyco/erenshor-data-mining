Please fix failing tests. This IS a critical issue!
Tests have to pass under ALL conditions (regular execution,
coverage reporting, ...).
Please add a pre-commit hook that checks for failing tests.

Please remove the environment variable configs.
NOW not later. It's just an unnecessary distraction
if we keep in the code base any longer than required.

Seems like the cli/main.py file is slowly getting
"too large". Please make a plan to properly split
it up, following best practices for CLI and project
structure design.

I'm somewhat hesitant about the resource name
normalization. If we do normalize resource names,
doesn't that prevent us from bi-directional
translation because the normalization is lossy?
Please check this.

Aren't there more readable names for the # noqa: ...
stuff? As a developer, I have no idea what, e.g.,
"PLR0915" means by just looking at it.

I'm not quite sure what the "is_manual" flag
is supposed to mean regarding wiki pages?
We have no way to know what's manually created
or not, do we? Is this supposed to be something
along the lines of "is_managed" (not sure about
the best terminology)? I.e., a page that is
(partially) "managed" / "updated" by our
automated wiki update system (i.e., a page
that contains entities that we have game
data for that allows us to do automatic
updates)? Please check this.

It's fine if we're not (yet) at 100% test
coverage. The system is still evolving heavily
and has quite a bit of placeholder code.
Just make sure to keep at it as we go.
Don't worry about the legacy code coverage at
all. All of that code will be removed once we're
done with the refactoring / rewrite.
No need to test concurrent operations either.
We will not use concurrency in the project.
Don't worry too much about integration tests
yet. Still have so many placeholders that we
can't really test integrations properly.

We do NOT need conflict severities.
All conflicts are equally important / relevant.
Please don't overcomplicate things (KISS / YAGNI).
