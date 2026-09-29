"""Future pass manager: track dependencies, context, requirements, observation
mappings, diagnostics and invalidated analyses across refinements. Separate
candidate search from acceptance. Preserve unknown/failed/unsupported outcomes.

Design obligations: docs/toolchain-contracts.md.
"""
