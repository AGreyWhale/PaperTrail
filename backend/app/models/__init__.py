"""
Every model must be imported here. `app.core.database` imports this
package at the bottom of the module, so anything listed below is
registered on Base.metadata by the time create_all() runs.
"""

from app.models.paper import Paper

__all__ = ["Paper"]
