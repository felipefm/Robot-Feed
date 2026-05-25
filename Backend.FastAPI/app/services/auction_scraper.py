"""
Serviço de Scraping de Leilões
Módulo de abstração para busca e extração de dados de leilões.

Este serviço fornece uma interface limpa para buscar, cachear e processar
leilões de múltiplos sites especializados.
"""

from typing import List, Dict, Any
from app.core.database import (
    buscar_lotes,
    LEILAO_URLS,
)

__all__ = [
    "search_auctions",
    "get_auction_urls",
]


def get_auction_urls() -> List[str]:
    """
    Retorna a lista de URLs de sites de leilão disponíveis.
    
    Útil para configuração dinâmica ou para verificar quais sites
    estão sendo monitorados.
    
    Returns:
        Lista de URLs de sites de leilão
    """
    return LEILAO_URLS.copy()


def search_auctions(termo: str) -> List[Dict[str, Any]]:
    """
    Busca leilões para um termo em todos os sites cadastrados.
    
    Utiliza cache automático para resultados já pesquisados e
    faz scraping apenas de sites novos.
    
    Args:
        termo: Termo de busca (ex: "ouro", "relógio antigo")
        
    Returns:
        Lista de dicionários com lotes encontrados, cada um contendo:
        - titulo: Título do lote
        - link: URL direto para o lote
        - imagem: URL da imagem do lote
        - valor: Valor atual/lance mínimo
        - lances: Número de lances recebidos
        - data_leilao: Data de encerramento do leilão
        
    Example:
        ```python
        lotes = search_auctions("ouro")
        for lote in lotes:
            print(f"{lote['titulo']} - {lote['valor']}")
        ```
    """
    all_lotes = []
    
    # Busca em todos os sites de leilão
    for url_template in LEILAO_URLS:
        # Substitui o placeholder {termo} pela busca formatada
        url = url_template.replace("{termo}", termo.replace(' ', '+'))
        
        try:
            # buscar_lotes() usa cache automaticamente
            lotes = buscar_lotes(url, termo)
            all_lotes.extend(lotes)
        except Exception as e:
            # Log implícito via buscar_lotes, continua com próximo site
            continue
    
    return all_lotes
