"""
Router de Endpoints de Leilões
Integração com app.core.database para busca, histórico e gerenciamento de leilões.
"""

import concurrent.futures
import logging
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from typing import List

# Importa modelos e funções do módulo core
from app.core.database import (
    AuctionItem,
    AuctionSearchRequest,
    AuctionHistoryItem,
    LEILAO_URLS,
    buscar_lotes,
    list_auctions_db,
    delete_all_lotes_db,
    delete_termo_db,
    delete_auction_item_db,
)

logger = logging.getLogger(__name__)

# ========== ROUTER ==========

router = APIRouter(prefix="/api", tags=["Auction"])


# ========== FUNÇÕES AUXILIARES ==========

def _execute_search(termos: List[str]) -> List[dict]:
    """
    Executa busca paralela de leilões em todos os sites para todos os termos.
    
    Args:
        termos: Lista de termos a buscar
        
    Returns:
        Lista de todos os lotes encontrados, ordenados por número de lances
    """
    tasks = []
    
    # Monta lista de (url, termo) para processar
    for termo in termos:
        for url_template in LEILAO_URLS:
            url = url_template.replace("{termo}", termo.replace(' ', '+'))
            tasks.append((url, termo))
    
    results = []
    
    # Executa buscas em paralelo com thread pool
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_task = {
            executor.submit(buscar_lotes, url, termo): (url, termo)
            for url, termo in tasks
        }
        
        # Coleta resultados conforme ficam prontos
        for future in concurrent.futures.as_completed(future_to_task):
            try:
                lotes = future.result()
                results.extend(lotes)
            except Exception as e:
                url, termo = future_to_task[future]
                logger.error(f"Erro ao buscar {termo} em {url}: {e}")
    
    # Ordena por número de lances (maior primeiro)
    results.sort(key=lambda x: x.get('lances', 0), reverse=True)
    
    return results


# ========== ENDPOINTS ==========

@router.post(
    "/auction/search",
    response_model=List[AuctionItem],
    summary="Buscar Leilões",
    description="Busca leilões em múltiplos sites para os termos fornecidos. Executa busca paralela para performance."
)
async def search_auctions_endpoint(payload: AuctionSearchRequest):
    """
    Realiza a busca de leilões para os termos fornecidos em todos os sites cadastrados.
    
    Executa busca paralela com thread pool para maior velocidade. Resultados são
    automaticamente salvos em cache para buscas futuras do mesmo termo/site.
    
    Args:
        payload: AuctionSearchRequest contendo lista de termos a buscar
        
    Returns:
        Lista de AuctionItem ordenada por número de lances (decrescente)
        
    Example:
        ```json
        {
            "terms": ["ouro", "relógio antigo"]
        }
        ```
    """
    termos = payload.terms
    
    if not termos:
        raise HTTPException(status_code=400, detail="Lista de termos não pode estar vazia")
    
    # Executa busca paralela em thread pool
    todos_resultados = await run_in_threadpool(_execute_search, termos)
    
    logger.info(f"Busca concluída para {len(termos)} termo(s): {len(todos_resultados)} lotes encontrados")
    
    return todos_resultados


@router.get(
    "/auction/history",
    response_model=List[AuctionHistoryItem],
    summary="Listar Histórico de Leilões",
    description="Retorna todos os itens de leilão salvos no histórico."
)
async def get_auction_history():
    """
    Retorna todos os itens de leilão salvos no banco de dados (histórico completo).
    
    Returns:
        Lista de AuctionHistoryItem com todos os leilões em cache
    """
    items = await run_in_threadpool(list_auctions_db)
    logger.info(f"Histórico recuperado: {len(items)} itens")
    return items


@router.get(
    "/auction/history/{termo}",
    response_model=List[AuctionHistoryItem],
    summary="Listar Histórico Filtrado",
    description="Retorna itens de leilão filtrados por um termo específico."
)
async def get_auction_history_by_term(termo: str):
    """
    Retorna itens de leilão salvos filtrados por um termo de busca específico.
    
    Args:
        termo: Termo para filtrar os resultados (busca parcial)
        
    Returns:
        Lista de AuctionHistoryItem apenas para o termo fornecido
    """
    items = await run_in_threadpool(list_auctions_db, termo)
    logger.info(f"Histórico filtrado por '{termo}': {len(items)} itens encontrados")
    return items


@router.delete(
    "/auction/history",
    summary="Limpar Histórico de Lotes",
    description="Remove todos os itens de leilão (lotes) do histórico, mas mantém os termos cadastrados."
)
async def delete_auction_history():
    """
    Remove todos os itens de leilão do histórico (lotes).
    
    ⚠️ NOTA: Os termos de busca são mantidos. Use DELETE /auction/terms para remover termos.
    
    Returns:
        Mensagem de confirmação
    """
    await run_in_threadpool(delete_all_lotes_db)
    logger.info("Histórico de leilões limpo com sucesso")
    return {"message": "Histórico de leilões limpo com sucesso."}


@router.delete(
    "/auction/terms",
    summary="Deletar Termos de Busca",
    description="Remove um ou todos os termos de busca e seus lotes associados."
)
async def delete_auction_terms(termo: str = None):
    """
    Remove termos de busca e seus lotes associados.
    
    Args:
        termo: Termo específico a deletar (opcional)
               Se omitido, deleta TODOS os termos e todos os lotes
    
    Returns:
        Mensagem de confirmação
        
    Example URLs:
        - `DELETE /auction/terms?termo=ouro` - Remove apenas "ouro"
        - `DELETE /auction/terms` - Remove TUDO
    """
    await run_in_threadpool(delete_termo_db, termo)
    
    if termo:
        msg = f"Termo '{termo}' e seus lotes foram deletados."
        logger.info(msg)
    else:
        msg = "Todos os termos e lotes foram deletados."
        logger.warning(msg)
    
    return {"message": msg}


@router.delete(
    "/auction/item/{item_id}",
    summary="Deletar Item de Leilão",
    description="Remove um item de leilão específico pelo ID."
)
async def delete_auction_item(item_id: int):
    """
    Remove um item de leilão específico pelo seu ID no banco de dados.
    
    Args:
        item_id: ID do item a ser removido
        
    Returns:
        Mensagem de confirmação
        
    Raises:
        HTTPException 404: Se o item com o ID fornecido não existir
        
    Example:
        `DELETE /auction/item/42` - Remove o item com ID 42
    """
    success = await run_in_threadpool(delete_auction_item_db, item_id)
    
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Item com ID {item_id} não encontrado no banco de dados."
        )
    
    logger.info(f"Item {item_id} deletado com sucesso")
    return {"message": f"Item {item_id} deletado com sucesso."}
