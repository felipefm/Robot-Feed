"""
Módulo Core - Componentes fundamentais da aplicação
"""

from .database import (
    init_db,
    salvar_cache_sqlite,
    buscar_cache_sqlite,
    list_auctions_db,
    delete_all_lotes_db,
    delete_termo_db,
    delete_auction_item_db,
    buscar_lotes,
    AuctionItem,
    AuctionSearchRequest,
    AuctionHistoryItem,
    LEILAO_URLS
)

from .llm_router import (
    read_prompt_from_file,
    call_llm_router,
    process_summary_text
)

__all__ = [
    # Database functions
    "init_db",
    "salvar_cache_sqlite",
    "buscar_cache_sqlite",
    "list_auctions_db",
    "delete_all_lotes_db",
    "delete_termo_db",
    "delete_auction_item_db",
    "buscar_lotes",
    "AuctionItem",
    "AuctionSearchRequest",
    "AuctionHistoryItem",
    "LEILAO_URLS",
    # LLM Router functions
    "read_prompt_from_file",
    "call_llm_router",
    "process_summary_text",
]
