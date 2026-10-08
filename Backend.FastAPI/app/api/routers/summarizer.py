"""
Router de Endpoints de Resumo (Summarizer)
Integração com YouTube, transcrições e roteador de IA para gerar resumos.
"""

import logging
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs
import time
import re

import yt_dlp
from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
    RequestBlocked,
)
import requests

# Importa funções do LLM router
from app.core.llm_router import (
    read_system_prompt_from_file,
    call_llm_router,
    process_youtube_summary,
)
from app.core.transcript_client import fetch_transcript

logger = logging.getLogger(__name__)

# ========== MODELOS PYDANTIC ==========

class VideoSummaryRequest(BaseModel):
    """Requisição para resumo de vídeo do YouTube."""
    video_url: str


class ManualTextRequest(BaseModel):
    """Requisição para resumo de texto manual."""
    title: str
    text: str


class VideoSummaryResponse(BaseModel):
    """Resposta com resumo de vídeo ou texto."""
    id: int | None = None
    url: str
    title: str | None = None
    transcript: str | None = None
    summary: str | None = None
    created_at: str
    channel_name: str | None = None
    video_upload_date: str | None = None
    thumbnail_url: str | None = None
    status: str
    error_log: str | None = None
    tokens_used: int | None = None
    provider: str | None = None


# ========== ROUTER ==========

router = APIRouter(prefix="/api", tags=["Video Summary"])


# ========== FUNÇÕES AUXILIARES ==========

def get_video_id_from_url(url: str) -> str | None:
    """
    Extrai o ID do vídeo a partir de uma URL do YouTube.
    
    Args:
        url: URL do YouTube (youtube.com/watch, youtu.be, embed, etc)
        
    Returns:
        ID do vídeo ou None se não conseguir extrair
        
    Example URLs:
        - https://www.youtube.com/watch?v=dQw4w9WgXcQ
        - https://youtu.be/dQw4w9WgXcQ
        - https://www.youtube.com/embed/dQw4w9WgXcQ
    """
    parsed_url = urlparse(url)
    
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            v_param = parse_qs(parsed_url.query).get('v')
            if v_param:
                return v_param[0]
        elif parsed_url.path.startswith('/embed/'):
            return parsed_url.path.split('/embed/')[1].split('?')[0]
    elif parsed_url.hostname in ('youtu.be', 'www.youtu.be'):
        return parsed_url.path[1:].split('?')[0]
    
    return None


def get_video_metadata(video_url: str) -> Dict[str, Any]:
    """
    Extrai metadados de um vídeo do YouTube (título, channel, data upload, thumbnail).
    
    Args:
        video_url: URL completa ou ID do vídeo
        
    Returns:
        Dicionário com:
        - title: Título do vídeo
        - channel_name: Nome do canal
        - video_upload_date: Data em formato YYYY-MM-DD
        - thumbnail_url: URL da thumbnail
        - video_id: ID extraído da URL
        
    Note:
        Em caso de erro, retorna um dict com valores None e o video_id se conseguir extrair.
    """
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'no_warnings': True,
        'extract_flat': False,  # Precisa de extração completa para metadados
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            
            # Tenta extrair e formatar a data de upload
            upload_date_raw = info.get('upload_date')
            upload_date_formatted = None
            if upload_date_raw:
                try:
                    upload_date_formatted = datetime.strptime(
                        upload_date_raw, '%Y%m%d'
                    ).strftime('%Y-%m-%d')
                except Exception:
                    upload_date_formatted = upload_date_raw

            return {
                "title": info.get('title'),
                "channel_name": info.get('uploader') or info.get('channel'),
                "video_upload_date": upload_date_formatted,
                "thumbnail_url": info.get('thumbnail'),
                "video_id": info.get('id') or get_video_id_from_url(video_url)
            }
    except Exception as e:
        logger.error(f"Erro ao extrair metadados para {video_url}: {e}")
        return {
            "title": None,
            "channel_name": None,
            "video_upload_date": None,
            "thumbnail_url": None,
            "video_id": get_video_id_from_url(video_url)
        }


def get_formatted_transcript(video_id: str) -> str:
    """
    Obtém a transcrição de um vídeo do YouTube com timestamps.
    
    Tenta primeiro em português, depois em inglês. Formato: [MM:SS] texto
    
    Args:
        video_id: ID do vídeo do YouTube
        
    Returns:
        Transcrição formatada com timestamps
        
    Raises:
        ValueError: Se a transcrição não estiver disponível
        
    Example:
        ```
        [00:12] Bem-vindo ao vídeo
        [00:45] Tema principal...
        ```
    """
    try:
        # Tenta baixar transcrição em português ou inglês
        transcript_list = fetch_transcript(video_id, languages=['pt', 'en'])
        
        formatted_segments = []
        for segment in transcript_list:
            try:
                # Tenta acessar como dicionário
                start_seconds = int(segment['start'])
                text = segment['text']
            except (TypeError, KeyError):
                # Tenta acessar como objeto com atributos
                try:
                    start_seconds = int(segment.start)
                    text = segment.text
                except AttributeError:
                    logger.error(
                        f"Segmento malformado (nem dict nem objeto): {segment}"
                    )
                    continue  # Pula segmento inválido
            
            # Converte segundos para MM:SS
            minutes = start_seconds // 60
            seconds = start_seconds % 60
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            formatted_segments.append(f"{timestamp} {text}")
        
        return "\n".join(formatted_segments)
        
    except NoTranscriptFound:
        raise ValueError("Nenhuma transcrição encontrada para este vídeo.")
    except TranscriptsDisabled:
        raise ValueError("Transcrições desativadas para este vídeo.")
    except VideoUnavailable:
        raise ValueError("Vídeo indisponível ou privado.")
    except RequestBlocked as e:
        # Cobre também IpBlocked (subclasse de RequestBlocked).
        logger.error(f"YouTube bloqueou a requisição de transcrição ({video_id}): {e}")
        raise ValueError(
            "YouTube bloqueou o IP do servidor para requisições de transcrição. "
            "Configure um proxy (WEBSHARE_PROXY_USERNAME/PASSWORD ou "
            "YTT_PROXY_HTTP_URL/YTT_PROXY_HTTPS_URL) para contornar o bloqueio."
        )
    except Exception as e:
        logger.error(f"Erro ao obter transcrição do vídeo {video_id}: {e}")
        raise ValueError(f"Falha ao recuperar transcrição: {e}")


def save_summary_to_db(
    url: str,
    transcript: str | None,
    summary: str | None,
    channel_name: str | None,
    video_upload_date: str | None,
    thumbnail_url: str | None,
    status: str,
    error_log: str | None,
    tokens_used: int | None,
    provider: str | None,
    title: str | None,
) -> int:
    """
    Salva um resumo no banco de dados do frontend via POST.
    
    Args:
        url: URL do vídeo ou ID manual
        transcript: Transcrição extraída
        summary: Resumo gerado
        channel_name: Nome do canal
        video_upload_date: Data de upload
        thumbnail_url: URL da thumbnail
        status: Status do processamento (Sucesso, Erro, Cota Esgotada)
        error_log: Mensagem de erro se houver
        tokens_used: Tokens consumidos pela IA
        provider: Nome do provedor (Gemini, Groq, etc)
        title: Título do vídeo/texto
        
    Returns:
        ID do resumo salvo no banco de dados do frontend
    """
    payload = {
        "video_id": url,
        "transcript": transcript,
        "summary": summary,
        "channel_name": channel_name,
        "video_upload_date": video_upload_date,
        "thumbnail_url": thumbnail_url,
        "status": status,
        "error_log": error_log,
        "tokens_used": tokens_used,
        "provider": provider,
        "title": title,
    }
    
    try:
        response = requests.post(
            "http://192.168.0.11:5000/archive-summary",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        
        # Tenta pegar ID retornado; caso contrário usa 1
        try:
            return response.json().get("id", 1)
        except ValueError:
            return 1
    except Exception as e:
        logger.error(f"Erro ao enviar resumo para frontend (URL {url}): {e}")
        return 1


# ========== ENDPOINTS ==========

@router.post(
    "/summarize-video",
    response_model=VideoSummaryResponse,
    summary="Resumir Vídeo do YouTube",
    description=(
        "Extrai transcrição de um vídeo do YouTube, gera resumo com IA e salva no banco. "
        "Usa roteamento em cascata de IA para melhor qualidade e redundância."
    ),
)
async def summarize_video_endpoint(request: VideoSummaryRequest):
    """
    Processa um vídeo do YouTube para gerar um resumo automático.
    
    Fluxo:
    1. Extrai metadados do vídeo (título, canal, data, thumbnail)
    2. Busca transcrição em português/inglês com timestamps
    3. Passa para roteador LLM em cascata (LM Studio → Gemini → Groq → DeepSeek → Mistral)
    4. Processa resumo (remove avisos, adiciona links clicáveis)
    5. Salva no banco de dados do frontend
    
    Args:
        request: VideoSummaryRequest com video_url
        
    Returns:
        VideoSummaryResponse com resumo completo
        
    Raises:
        HTTPException 400: URL inválida ou ID não extraível
        HTTPException 429: Limite de cota atingido
        HTTPException 500: Erro interno
        
    Example:
        ```json
        {
            "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        }
        ```
    """
    video_url = request.video_url
    
    # Inicializa resposta com status de erro
    response_data = VideoSummaryResponse(
        url=video_url,
        created_at=datetime.now(timezone.utc).isoformat(),
        status="Erro",
        error_log="Processamento iniciado com erro desconhecido.",
    )
    video_id = None

    try:
        # 1. Extrai metadados do vídeo
        metadata = await run_in_threadpool(get_video_metadata, video_url)
        video_id = metadata.get("video_id")
        
        if not video_id:
            raise HTTPException(
                status_code=400,
                detail="Não foi possível extrair o ID do vídeo da URL fornecida.",
            )
        
        response_data.title = metadata.get("title")
        response_data.channel_name = metadata.get("channel_name")
        response_data.video_upload_date = metadata.get("video_upload_date")
        response_data.thumbnail_url = metadata.get("thumbnail_url")

        # 2. Obtém transcrição formatada
        formatted_transcript = await run_in_threadpool(
            get_formatted_transcript, video_id
        )
        response_data.transcript = formatted_transcript

        # 3. Lê prompt customizado
        system_prompt = await run_in_threadpool(read_system_prompt_from_file)

        # 4. Roteamento LLM em cascata
        llm_result = await run_in_threadpool(
            call_llm_router, system_prompt, formatted_transcript
        )
        
        # 5. Processa resumo (remove avisos, adiciona links)
        raw_summary = llm_result["summary"]
        processed_summary = process_youtube_summary(raw_summary, video_id)
        
        # 6. Preenche dados de sucesso
        response_data.summary = processed_summary
        response_data.tokens_used = llm_result.get("tokens_used")
        response_data.provider = llm_result.get("provider")
        response_data.status = "Sucesso"
        response_data.error_log = None

    except HTTPException as e:
        response_data.error_log = e.detail
        raise e
    except ValueError as e:
        response_data.error_log = str(e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "resource_exhausted" in error_str or "quota" in error_str:
            response_data.status = "Cota Esgotada"
            response_data.error_log = "Limite de cota da API atingido (429)."
            raise HTTPException(
                status_code=429,
                detail="Limite de cota da API atingido (Resource Exhausted).",
            )
        else:
            response_data.error_log = f"Erro interno do servidor: {e}"
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao processar vídeo: {e}",
            )
    finally:
        # 7. Sempre salva no banco (sucesso ou erro)
        saved_id = await run_in_threadpool(
            save_summary_to_db,
            video_id or response_data.url,
            response_data.transcript,
            response_data.summary,
            response_data.channel_name,
            response_data.video_upload_date,
            response_data.thumbnail_url,
            response_data.status,
            response_data.error_log,
            response_data.tokens_used,
            response_data.provider,
            response_data.title,
        )
        if saved_id != -1:
            response_data.id = saved_id
        
    return response_data


@router.post(
    "/summarize-text",
    response_model=VideoSummaryResponse,
    summary="Resumir Texto Manual",
    description=(
        "Gera resumo de um texto colado manualmente usando roteador LLM em cascata."
    ),
)
async def summarize_text_endpoint(request: ManualTextRequest):
    """
    Processa um texto manualmente fornecido para gerar resumo automático.
    
    Fluxo:
    1. Recebe título e corpo do texto
    2. Passa para roteador LLM em cascata
    3. Salva no banco de dados do frontend
    
    Args:
        request: ManualTextRequest com title e text
        
    Returns:
        VideoSummaryResponse com resumo
        
    Raises:
        HTTPException 400: Texto vazio ou inválido
        HTTPException 429: Limite de cota atingido
        HTTPException 500: Erro interno
        
    Example:
        ```json
        {
            "title": "Artigo sobre Python",
            "text": "Python é uma linguagem de programação..."
        }
        ```
    """
    # Gera URL única para texto manual
    manual_url = f"manual_{int(time.time())}"
    
    # Inicializa resposta com status de erro
    response_data = VideoSummaryResponse(
        url=manual_url,
        title=request.title,
        transcript=request.text,  # Texto original no campo transcript
        created_at=datetime.now(timezone.utc).isoformat(),
        channel_name="Manual Input",
        status="Erro",
        error_log="Processamento iniciado com erro desconhecido.",
    )

    try:
        # 1. Define prompt para texto manual
        prompt_text = "Resumir o texto colado manualmente."

        # 2. Roteamento LLM em cascata
        llm_result = await run_in_threadpool(
            call_llm_router, prompt_text, request.text
        )
        
        # 3. Preenche dados de sucesso
        response_data.summary = llm_result["summary"]
        response_data.tokens_used = llm_result.get("tokens_used")
        response_data.provider = llm_result.get("provider")
        response_data.status = "Sucesso"
        response_data.error_log = None

    except ValueError as e:
        response_data.error_log = str(e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        error_str = str(e).lower()
        if "429" in error_str or "resource_exhausted" in error_str or "quota" in error_str:
            response_data.status = "Cota Esgotada"
            response_data.error_log = "Limite de cota da API atingido (429)."
            raise HTTPException(
                status_code=429,
                detail="Limite de cota da API atingido (Resource Exhausted).",
            )
        else:
            response_data.error_log = f"Erro interno do servidor: {e}"
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao processar texto: {e}",
            )
    finally:
        # 4. Sempre salva no banco (sucesso ou erro)
        saved_id = await run_in_threadpool(
            save_summary_to_db,
            url=response_data.url,
            transcript=response_data.transcript,
            summary=response_data.summary,
            channel_name=response_data.channel_name,
            video_upload_date=None,  # Sem data para texto manual
            thumbnail_url=None,  # Sem thumbnail
            status=response_data.status,
            error_log=response_data.error_log,
            tokens_used=response_data.tokens_used,
            provider=response_data.provider,
            title=response_data.title,
        )
        if saved_id != -1:
            response_data.id = saved_id
        
    return response_data
