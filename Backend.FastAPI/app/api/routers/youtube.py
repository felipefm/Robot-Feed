"""
Router de Endpoints do YouTube
Integração com scraper.py para verificação de canais ao vivo e metadados.
"""

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import List
import asyncio
import logging

# Importa funções do scraper
from app.services.youtube_scraper import (
    is_channel_live, 
    get_channel_details, 
    get_live_stream_duration, 
    process_youtube_clip
)

logger = logging.getLogger(__name__)

# ========== MODELOS PYDANTIC ==========

class LiveStatusResponse(BaseModel):
    """Resposta de status ao vivo de um canal."""
    channel_name: str
    is_live: bool
    status: str
    video_id: str | None = None


class ChannelList(BaseModel):
    """Lista de IDs de canais para verificação em lote."""
    channel_ids: List[str]


class ChannelDetailsResponse(BaseModel):
    """Detalhes de um canal do YouTube."""
    id: str
    title: str


class LiveDurationResponse(BaseModel):
    """Informações de duração de uma live."""
    video_id: str
    start_time: str
    duration_seconds: int
    duration_str: str


# ========== ROUTER ==========

router = APIRouter(prefix="/api", tags=["YouTube"])


# ========== ENDPOINTS ==========

@router.get(
    "/get-channel-details/{identifier}",
    response_model=ChannelDetailsResponse,
    tags=["Channel Details"],
    summary="Buscar Detalhes do Canal",
    description="Obtém ID e título de um canal usando handle (@username) ou ID direto."
)
async def get_channel_details_endpoint(identifier: str):
    """
    Busca os detalhes de um canal (ID e Título) a partir de um handle ou ID.
    
    Args:
        identifier: Handle (@username) ou ID do canal
        
    Returns:
        ChannelDetailsResponse com id e title
        
    Raises:
        HTTPException 404: Se o canal não for encontrado
    """
    details = await run_in_threadpool(get_channel_details, identifier)
    if not details:
        raise HTTPException(status_code=404, detail="Canal não encontrado")
    return details


@router.get(
    "/check-live/{channel_identifier}",
    response_model=LiveStatusResponse,
    tags=["Live Status"],
    summary="Verificar Status Ao Vivo",
    description="Verifica se um canal está transmitindo ao vivo no momento."
)
async def check_live_status(channel_identifier: str):
    """
    Verifica o status ao vivo de um único canal do YouTube, usando ID ou handle.
    
    Args:
        channel_identifier: ID ou handle do canal
        
    Returns:
        LiveStatusResponse com status (Live/Offline) e video_id se estiver ao vivo
    """
    is_live, video_id = await run_in_threadpool(is_channel_live, channel_identifier)
    return {
        "channel_name": channel_identifier,
        "is_live": is_live,
        "status": "Live" if is_live else "Offline",
        "video_id": video_id
    }


@router.post(
    "/check-live-batch",
    response_model=List[LiveStatusResponse],
    tags=["Live Status"],
    summary="Verificar Status Ao Vivo em Lote",
    description="Verifica o status de múltiplos canais simultaneamente (mais eficiente)."
)
async def check_live_status_batch(payload: ChannelList):
    """
    Verifica o status ao vivo de uma lista de canais do YouTube em lote.
    Executa requisições em paralelo para melhor performance.
    
    Args:
        payload: ChannelList com lista de IDs de canais
        
    Returns:
        Lista de LiveStatusResponse, um por canal
    """
    # Cria tasks assíncronas para cada canal
    tasks = [
        run_in_threadpool(is_channel_live, channel_id)
        for channel_id in payload.channel_ids
    ]
    
    # Executa todas em paralelo
    results = await asyncio.gather(*tasks)

    # Monta a resposta
    response_data = []
    for i, (is_live, video_id) in enumerate(results):
        channel_id = payload.channel_ids[i]
        response_data.append({
            "channel_name": channel_id,
            "is_live": is_live,
            "status": "Live" if is_live else "Offline",
            "video_id": video_id
        })
    
    return response_data


@router.get(
    "/get-live-duration",
    response_model=LiveDurationResponse,
    tags=["Live Details"],
    summary="Obter Duração da Live",
    description="Calcula há quanto tempo uma transmissão ao vivo está no ar."
)
async def get_live_duration_endpoint(video_url: str):
    """
    Calcula há quanto tempo uma live está no ar, dado a URL ou ID do vídeo.
    
    Args:
        video_url: URL completa ou ID do vídeo do YouTube
        
    Returns:
        LiveDurationResponse com video_id, start_time e durações
        
    Raises:
        HTTPException 404: Se o vídeo não for encontrado ou não tiver start_time
    """
    # O scraper lida com a extração do ID da URL
    details = await run_in_threadpool(get_live_stream_duration, video_url)
    
    if not details:
        raise HTTPException(
            status_code=404,
            detail="Vídeo não encontrado ou horário de início não disponível"
        )
    
    return details

class ClipRequest(BaseModel):
    """Payload para solicitar o corte de um vídeo e transcrição."""
    video_url: str
    start_time: str  # Ex: "01:20" ou "30"
    end_time: str    # Ex: "02:45" ou "120"

class ClipResponse(BaseModel):
    """Resposta com os caminhos dos arquivos gerados e uma prévia do texto."""
    message: str
    video_file_path: str
    txt_file_path: str
    transcript_text: str

@router.post(
    "/create-clip",
    response_model=ClipResponse,
    tags=["Video Processing"],
    summary="Criar Clip de Vídeo e Transcrição",
    description="Corta um trecho específico de um vídeo e gera um TXT da transcrição correspondente."
)
async def create_video_clip_endpoint(payload: ClipRequest):
    """
    Recebe a URL de um vídeo, o tempo inicial e final, e gera o recorte.
    """
    try:
        # Executa em uma thread separada porque o download bloqueia o servidor
        resultado = await run_in_threadpool(
            process_youtube_clip, 
            payload.video_url, 
            payload.start_time, 
            payload.end_time
        )
        
        return {
            "message": "Clip gerado com sucesso!",
            "video_file_path": resultado["video_path"],
            "txt_file_path": resultado["txt_path"],
            "transcript_text": resultado["transcript_preview"]
        }
        
    except Exception as e:
        logger.error(f"Erro ao processar o clip: {e}")
        raise HTTPException(status_code=500, detail=str(e))