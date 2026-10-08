"""
Routers - Endpoints organizados por funcionalidade
Cada router é um módulo independente com seus próprios endpoints.
"""

from . import youtube, auctions, summarizer, documents

__all__ = ["youtube", "auctions", "summarizer", "documents"]
