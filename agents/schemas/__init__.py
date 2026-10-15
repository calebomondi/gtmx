"""Single source of truth for every pydantic/TypedDict model the agents use.

Import from the domain module (`from agents.schemas.icp import ICP`); this
package deliberately re-exports nothing, so each model has one import path.
"""
