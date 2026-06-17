"""Property-based tests using Hypothesis (#1920).

Each module tests an invariant property of a critical schema or function
by generating arbitrary valid inputs with Hypothesis and asserting that
the invariant holds for all of them.
"""