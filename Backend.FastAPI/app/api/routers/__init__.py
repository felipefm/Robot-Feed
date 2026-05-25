"""
Routers - Endpoints organizados por funcionalidade
Cada router é um módulo independente com seus próprios endpoints.
"""

from . import youtube, correios, auctions, summarizer, documents

__all__ = ["youtube", "correios", "auctions", "summarizer", "documents"]
