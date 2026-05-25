"""
Pacote de Serviços
Contém a lógica de negócio isolada de routers e banco de dados.

Estrutura:
- auction_scraper: Serviço de busca e scraping de leilões
"""

from . import auction_scraper

__all__ = ["auction_scraper"]
