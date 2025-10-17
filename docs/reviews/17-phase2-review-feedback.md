Can ruff do import ordering?
Or do we need a separate tool such as isort?  

We don't yet have all functionality implemented,
so can't do useful E2E testing. Integration testing
is not fully doable either.

We don't need concurrent operation testing because
we won't have any concurrency in the final project.
Please keep things simple.

VCR.py sounds interesting! Please put that on the backlog.
Performance tests proably aren't so useful for our use case.
