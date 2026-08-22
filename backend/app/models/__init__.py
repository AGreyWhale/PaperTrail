"""
Every model must be imported here. `app.core.database` imports this
package at the bottom of the module, so anything listed below is
registered on Base.metadata by the time create_all() runs.
"""
from app.models.chunk import Chunk
from app.models.collection import Collection, collection_papers
from app.models.note import Note
from app.models.paper import Paper
from app.models.tag import Tag, paper_tags

__all__ = ["Chunk", "Collection", "Note", "Paper", "Tag", "collection_papers", "paper_tags"]
