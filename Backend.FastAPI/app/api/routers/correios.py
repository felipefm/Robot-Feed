"""
Router de Endpoints dos Correios
Integração com correios_scraper.py para rastreamento de encomendas.
"""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Dict, Any
import logging

# Importa função do scraper de correios
from correios_scraper import fetch_tracking_data

logger = logging.getLogger(__name__)

# ========== MODELOS PYDANTIC ==========

class CorreiosTrackRequest(BaseModel):
    """Requisição de rastreamento nos Correios."""
    object_code: str


# ========== ROUTER ==========

router = APIRouter(prefix="/api", tags=["Correios"])


# ========== ENDPOINTS ==========

@router.post(
    "/correios/track",
    tags=["Correios"],
    summary="Rastrear Encomenda",
    description="Consulta o status de rastreamento de uma encomenda nos Correios via SeuRastreio.",
    response_model=Dict[str, Any]
)
async def track_correios_object(payload: CorreiosTrackRequest):
    """
    Realiza a consulta do objeto nos Correios via API do SeuRastreio.
    
    Args:
        payload: CorreiosTrackRequest contendo code da encomenda
        
    Returns:
        Dicionário com informações de rastreamento
        
    Raises:
        HTTPException 504: Se houver timeout na requisição
        HTTPException 400: Se houver erro na API ou código inválido
    """
    result = await run_in_threadpool(fetch_tracking_data, payload.object_code)
    
    if "error" in result:
        # Se for timeout, retorna 504 (Gateway Timeout), caso contrário 400
        status_code = 504 if "Timeout" in result["error"] else 400
        error_detail = result.get("message") or result["error"]
        raise HTTPException(status_code=status_code, detail=error_detail)
    
    return result
