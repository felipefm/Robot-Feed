from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from typing import List, Dict

from app.services import music_service, playlist_manager

router = APIRouter(
    prefix="/music",
    tags=["Music & Playlists"]
)

logger = logging.getLogger(__name__)

class PlaylistGenerateRequest(BaseModel):
    user_mood: str
    playlist_name: str

@router.get("/library")
def get_music_library() -> List[Dict[str, str]]:
    """
    Retorna a biblioteca de músicas mapeada do Plex.
    """
    try:
        return music_service.list_music_library()
    except Exception as e:
        logger.error(f"Erro ao obter biblioteca de música: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/playlist/generate")
def generate_playlist(request: PlaylistGenerateRequest):
    """
    Gera uma playlist baseada no humor (mood) fornecido usando IA e salva em .m3u8.
    """
    try:
        # Valida conexão com Plex
        if not music_service.validate_plex_connection():
            raise HTTPException(status_code=500, detail="Erro de conexão com o Plex.")
        
        # 1. Gera a lista de caminhos de arquivo baseada no mood
        logger.info(f"Gerando playlist para o mood: {request.user_mood}")
        music_paths = music_service.generate_playlist_from_mood(request.user_mood)
        
        if not music_paths:
            raise HTTPException(status_code=404, detail="Nenhuma música encontrada para o mood fornecido.")
        
        # 2. Salva a playlist
        logger.info(f"Salvando playlist: {request.playlist_name}")
        filepath = playlist_manager.save_playlist(music_paths, request.playlist_name)
        
        return {
            "message": "Playlist gerada e salva com sucesso.",
            "filepath": filepath,
            "track_count": len(music_paths),
            "tracks": music_paths
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Erro ao gerar/salvar playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/playlists")
def list_playlists() -> List[str]:
    """
    Lista todas as playlists geradas (.m3u8).
    """
    try:
        return playlist_manager.list_existing_playlists()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/playlists/{filename}")
def get_playlist_details(filename: str):
    """
    Obtém detalhes de uma playlist específica.
    """
    try:
        info = playlist_manager.get_playlist_info(filename)
        if not info:
            raise HTTPException(status_code=404, detail="Playlist não encontrada.")
        return info
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/playlists/{filename}")
def delete_playlist(filename: str):
    """
    Deleta uma playlist específica.
    """
    try:
        success = playlist_manager.delete_playlist(filename)
        if not success:
            raise HTTPException(status_code=404, detail="Playlist não encontrada ou erro ao deletar.")
        return {"message": f"Playlist {filename} deletada com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
