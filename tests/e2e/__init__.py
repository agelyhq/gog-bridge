"""A package, so this directory's conftest imports as e2e.conftest.

Without it pytest would load both conftest modules under the bare name
`conftest`, and the unit tier's `from conftest import ...` would land here.
"""
