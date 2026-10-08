"""
Serviço de Música - Integração com Plex e LLM Router
Responsável por ler biblioteca de música e gerar playlists inteligentes usando IA.
"""

import os
import json
import logging
from typing import Dict, List, Tuple
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound

from app.core.llm_router import call_llm_router

logger = logging.getLogger(__name__)

# ========== CONFIGURAÇÕES ==========

PLEX_URL = os.getenv("PLEX_URL", "http://localhost:32400")
PLEX_TOKEN = os.getenv("PLEX_TOKEN")
MUSIC_LIBRARY_NAME = os.getenv("PLEX_MUSIC_LIBRARY", "Músicas")


# ========== FUNÇÕES AUXILIARES ==========

def _connect_to_plex() -> PlexServer:
    """
    Conecta ao servidor Plex usando variáveis de ambiente.
    
    Returns:
        Instância de PlexServer conectada
        
    Raises:
        ValueError: Se URL ou token não estiverem configurados
        Unauthorized: Se as credenciais forem inválidas
    """
    if not PLEX_URL or not PLEX_TOKEN:
        raise ValueError(
            "Configuração do Plex incompleta. Defina PLEX_URL e PLEX_TOKEN."
        )
    
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        logger.info(f"Conectado ao Plex: {plex.friendlyName}")
        return plex
    except Unauthorized:
        raise Unauthorized(f"Token inválido para {PLEX_URL}")
    except Exception as e:
        raise ConnectionError(f"Erro ao conectar ao Plex: {e}")

# ========== LÓGICA PARA CRIAR PLAYLIST ==========

def get_plex_library_mapped() -> Tuple[str, Dict[int, Dict[str, str]]]:
    """
    Varre a biblioteca de música do Plex e cria um mapeamento com IDs temporários.
    
    Estratégia de economia de tokens:
    - Não envia caminhos de arquivo para a IA
    - Cria IDs sequenciais (1, 2, 3...)
    - Mapeia internamente ID -> caminho físico
    """
    plex = _connect_to_plex()
    
    try:
        music_library = plex.library.section(MUSIC_LIBRARY_NAME)
    except NotFound:
        raise ValueError(
            f"Biblioteca '{MUSIC_LIBRARY_NAME}' não encontrada no Plex. "
            f"Bibliotecas disponíveis: {[lib.title for lib in plex.library.sections()]}"
        )
    
    # CORREÇÃO: Usar searchTracks() em vez de all()
    tracks = music_library.searchTracks()
    
    if not tracks:
        raise ValueError(f"Biblioteca '{MUSIC_LIBRARY_NAME}' está vazia.")
    
    library_map = {}
    library_string_parts = []
    
    for idx, track in enumerate(tracks, start=1):
        try:
            artist = track.originalTitle or track.grandparentTitle or "Desconhecido"
            title = track.title
            
            # Extração blindada do caminho do arquivo (igual ao debug)
            file_path = None
            try:
                if track.media and len(track.media) > 0:
                    if track.media[0].parts and len(track.media[0].parts) > 0:
                        file_path = track.media[0].parts[0].file
            except Exception:
                pass 
            
            if not file_path:
                continue
            
            # Monta o mapeamento
            library_map[idx] = {
                "artist": artist,
                "title": title,
                "file": file_path,
                "plex_track": track
            }
            
            # Monta a string ultracompacta para a IA
            library_string_parts.append(f"{idx}: {artist} - {title}")
            
        except Exception as e:
            logger.warning(f"Erro ao processar track: {e}")
            continue
    
    if not library_map:
        raise ValueError("Nenhuma track com caminho de arquivo disponível. Verifique a estrutura da biblioteca.")
    
    library_string = "\n".join(library_string_parts)
    logger.info(f"Biblioteca mapeada para IA: {len(library_map)} tracks")
    
    return library_string, library_map


# ========== LÓGICA PRINCIPAL ==========

def generate_playlist_from_mood(user_mood: str) -> List[str]:
    """
    Gera uma playlist inteligente baseada no mood do usuário.
    
    Fluxo:
    1. Obtém biblioteca do Plex com mapeamento de IDs
    2. Envia apenas IDs e metadados leves para a IA
    3. Força IA a retornar JSON array de IDs
    4. Decodifica resposta e mapeia para caminhos físicos
    
    Args:
        user_mood: Descrição do mood/contexto (ex: "Música para trabalhar")
        
    Returns:
        Lista de caminhos de arquivo completos das músicas selecionadas
        
    Raises:
        ValueError: Se a IA não retornar JSON válido ou biblioteca estiver vazia
        ConnectionError: Se houver erro de conectividade
    """
    # 1. Obtém biblioteca e mapeamento
    library_string, library_map = get_plex_library_mapped()
    
    # 2. Define o system_prompt que força JSON na resposta
    system_prompt = (
        "Você é um curador de música especializado em criar playlists. "
        "Baseado no mood fornecido, selecione as músicas mais apropriadas da biblioteca. "
        "IMPORTANTE: Retorne APENAS um array JSON com os IDs das músicas selecionadas, "
        "sem nenhum texto adicional. Exemplo: [1, 5, 12, 23]. "
        "Selecione entre 5 e 20 músicas que melhor correspondem ao mood."
    )
    
    # 3. Monta o user_content com a biblioteca e o mood
    user_content = (
        f"Biblioteca de Músicas Disponíveis:\n{library_string}\n\n"
        f"Mood Desejado: {user_mood}"
    )
    
    # 4. Chama o LLM router
    try:
        llm_result = call_llm_router(system_prompt, user_content)
        response_text = llm_result["summary"]
        provider = llm_result.get("provider", "Unknown")
        logger.info(f"Resposta recebida do provider: {provider}")
    except Exception as e:
        raise ConnectionError(f"Erro ao chamar LLM router: {e}")
    
    # 5. Extrai JSON da resposta
    selected_ids = _extract_json_array(response_text)
    
    if not selected_ids:
        raise ValueError(
            f"IA não retornou JSON válido. Resposta: {response_text[:200]}"
        )
    
    # 6. Valida IDs e mapeia para caminhos
    playlist_paths = []
    plex_tracks = []
    invalid_ids = []
    
    for track_id in selected_ids:
        if isinstance(track_id, int) and track_id in library_map:
            file_path = library_map[track_id]["file"]
            playlist_paths.append(file_path)
            
            # Coleta o objeto nativo do Plex
            plex_tracks.append(library_map[track_id]["plex_track"]) # <--- ADICIONE ESTA LINHA
        else:
            invalid_ids.append(track_id)
    
    if invalid_ids:
        logger.warning(
            f"IDs inválidos ignorados: {invalid_ids}. "
            f"Total válidos: {len(playlist_paths)}"
        )
    
    if not playlist_paths:
        raise ValueError(f"Nenhum ID válido foi retornado pela IA. IDs recebidos: {selected_ids}")
    
    # =====================================================================
    # A MÁGICA DO PLEX: CRIA A PLAYLIST NATIVAMENTE VIA API
    # =====================================================================
    if plex_tracks:
        try:
            plex = _connect_to_plex()
            # Gera um nome limpo para aparecer no Plex
            plex_playlist_name = f"IA - {user_mood[:30]}"
            plex.createPlaylist(title=plex_playlist_name, items=plex_tracks)
            logger.info(f"Playlist '{plex_playlist_name}' injetada nativamente no Plex com sucesso!")
        except Exception as e:
            logger.error(f"Erro ao injetar playlist no Plex: {e}")
    # =====================================================================

    logger.info(f"Playlist gerada: {len(playlist_paths)} músicas para mood '{user_mood}'")
    return playlist_paths


def _extract_json_array(text: str) -> List[int]:
    """
    Extrai um array JSON de inteiros de um texto.
    
    Tenta localizar um padrão [1, 2, 3] mesmo que haja texto adicional.
    
    Args:
        text: Texto que pode conter JSON array
        
    Returns:
        Lista de inteiros, ou lista vazia se não encontrar formato válido
    """
    # Limpa o texto
    text = text.strip()
    
    # Tenta parsejar direto (resposta ideal)
    try:
        data = json.loads(text)
        if isinstance(data, list) and all(isinstance(x, int) for x in data):
            return data
    except json.JSONDecodeError:
        pass
    
    # Tenta encontrar padrão [num, num, ...] no texto
    import re
    match = re.search(r'\[[\d\s,]+\]', text)
    if match:
        try:
            data = json.loads(match.group())
            if isinstance(data, list) and all(isinstance(x, int) for x in data):
                return data
        except json.JSONDecodeError:
            pass
    
    # Nenhum formato válido encontrado
    logger.error(f"Não foi possível extrair JSON array de: {text}")
    return []


# ========== UTILITÁRIOS ==========

def list_music_library():
    """
    Função de leitura blindada com debug para o Plex.
    """
    try:
        plex = PlexServer(PLEX_URL, PLEX_TOKEN)
        music_library = plex.library.section(MUSIC_LIBRARY_NAME)
    except Exception as e:
        logger.error(f"Erro ao acessar a biblioteca '{MUSIC_LIBRARY_NAME}': {e}")
        raise ValueError(f"Não foi possível encontrar a biblioteca '{MUSIC_LIBRARY_NAME}' no Plex.")

    tracks = music_library.searchTracks()
    logger.info(f"O Plex retornou {len(tracks)} músicas na biblioteca '{MUSIC_LIBRARY_NAME}'.")

    if not tracks:
        raise ValueError(f"A biblioteca '{MUSIC_LIBRARY_NAME}' foi encontrada, mas está vazia (0 tracks).")

    valid_tracks = []
    
    # Vamos logar apenas as primeiras 5 falhas para não floodar o seu terminal
    fail_log_count = 0 

    for track in tracks:
        file_path = None
        
        # Tenta extrair o caminho físico do arquivo da forma padrão do PlexAPI
        try:
            if track.media and len(track.media) > 0:
                if track.media[0].parts and len(track.media[0].parts) > 0:
                    file_path = track.media[0].parts[0].file
        except Exception as e:
            pass # Ignora o erro estrutural e tenta tratar abaixo
            
        if file_path:
            valid_tracks.append({
                "artist": track.originalTitle or track.grandparentTitle or "Desconhecido",
                "title": track.title,
                "path": file_path
            })
        else:
            if fail_log_count < 5:
                logger.warning(f"DEBUG: Música '{track.title}' encontrada, mas sem 'part.file'. Estrutura da media: {track.media}")
                fail_log_count += 1

    if not valid_tracks:
        raise ValueError("Nenhuma track com caminho de arquivo disponível. Verifique os logs do backend.")

    logger.info(f"Sucesso: {len(valid_tracks)} músicas válidas mapeadas.")
    return valid_tracks

def validate_plex_connection() -> bool:
    """
    Valida se a conexão ao Plex está funcionando.
    
    Returns:
        True se conectado com sucesso, False caso contrário
    """
    try:
        plex = _connect_to_plex()
        logger.info("Plex validado com sucesso")
        return True
    except Exception as e:
        logger.error(f"Falha na validação do Plex: {e}")
        return False
