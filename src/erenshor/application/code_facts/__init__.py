"""Extract hardcoded game constants from the shipped assembly into the raw DB.

Entry point: :func:`erenshor.application.code_facts.runner.extract_code_facts`.
"""

from erenshor.application.code_facts.runner import extract_code_facts

__all__ = ["extract_code_facts"]
