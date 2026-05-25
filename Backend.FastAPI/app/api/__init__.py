"""
Pacote API - Routers e Endpoints
Contém todos os roteadores da aplicação.
"""

from .routers import youtube, correios, auctions, summarizer, documents

__all__ = ["youtube", "correios", "auctions", "summarizer", "documents"]
