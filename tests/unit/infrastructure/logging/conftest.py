"""Pytest configuration for logging tests.

This conftest prevents the root conftest.py from being loaded,
which may have dependencies on modules not yet implemented.
"""

# This empty conftest stops pytest from traversing up to parent conftest.py
