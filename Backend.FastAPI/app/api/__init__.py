"""
Pacote API - Routers e Endpoints
Contém todos os roteadores da aplicação.
"""

from .routers import youtube, auctions, summarizer, documents

__all__ = ["youtube", "auctions", "summarizer", "documents"]
