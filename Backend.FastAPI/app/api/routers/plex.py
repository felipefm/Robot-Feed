from fastapi import APIRouter, HTTPException
from plexapi.server import PlexServer
import logging
import os # <-- Adicionar isso

router = APIRouter(
    prefix="/plex",
    tags=["Plex Media Server"]
)

logger = logging.getLogger(__name__)

# Puxando as variáveis de ambiente com um fallback (valor padrão) seguro
PLEX_URL = os.getenv('PLEX_URL', 'http://192.168.0.11:32400')
PLEX_TOKEN = os.getenv('PLEX_TOKEN') # <-- Agora está seguro
NOME_BIBLIOTECA = os.getenv('PLEX_LIBRARY_NAME', 'Desenhos')

@router.get("/listar-bibliotecas")
def listar_bibliotecas():
    """
    Endpoint de diagnóstico para listar exatamente os nomes das bibliotecas
    que o Plex está retornando para a API.
    """
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        # Puxa o título de todas as bibliotecas visíveis com esse Token
        secoes = [secao.title for secao in plex.library.sections()]
        
        return {
            "mensagem": "Conexão bem sucedida!",
            "bibliotecas_encontradas": secoes
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")

@router.delete("/limpar-assistidos")
def limpar_videos_assistidos():
    if not PLEX_TOKEN:
        raise HTTPException(status_code=500, detail="Token do Plex não configurado no .env")
    """
    Conecta ao Plex via rede e solicita a exclusão de vídeos já assistidos.
    """
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        biblioteca = plex.library.section(NOME_BIBLIOTECA)
        videos = biblioteca.all()
        
        apagados = []
        for video in videos:
            if video.isPlayed:
                nome_video = video.title
                # O comando abaixo instrui o PLEX a apagar o arquivo do disco
                video.delete() 
                apagados.append(nome_video)
                logger.info(f"Vídeo apagado via API: {nome_video}")
                
        if not apagados:
            return {"message": "Nenhum vídeo assistido encontrado para exclusão.", "apagados": []}
            
        return {"message": f"{len(apagados)} vídeos foram excluídos com sucesso.", "apagados": apagados}

    except Exception as e:
        logger.error(f"Erro ao comunicar com o Plex: {e}")
        raise HTTPException(status_code=500, detail=f"Erro de comunicação com o Plex: {e}")