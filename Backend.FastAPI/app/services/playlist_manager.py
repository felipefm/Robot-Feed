"""
Gerenciador de Playlists - I/O de Playlists
Responsável por salvar listas de músicas em formato .m3u8 compatível com Plex, Jellyfin e Swing Music.
"""

import os
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# ========== CONFIGURAÇÕES ==========

PLAYLIST_FOLDER_PATH = os.getenv("PLAYLIST_FOLDER_PATH", "/MusicPlex/Playlists_IA")


# ========== FUNÇÕES AUXILIARES ==========

def _ensure_playlist_folder_exists() -> str:
    """
    Garante que o diretório de playlists existe.
    Cria recursivamente se necessário.
    
    Returns:
        Caminho absoluto do diretório de playlists
        
    Raises:
        PermissionError: Se não houver permissão para criar o diretório
    """
    try:
        Path(PLAYLIST_FOLDER_PATH).mkdir(parents=True, exist_ok=True)
        logger.info(f"Diretório de playlists validado: {PLAYLIST_FOLDER_PATH}")
        return PLAYLIST_FOLDER_PATH
    except PermissionError:
        raise PermissionError(
            f"Permissão negada ao criar/acessar diretório: {PLAYLIST_FOLDER_PATH}"
        )
    except Exception as e:
        raise OSError(f"Erro ao criar diretório de playlists: {e}")


def _sanitize_filename(text: str) -> str:
    """
    Limpa um texto para ser usado como nome de arquivo.
    Remove caracteres especiais e espaços múltiplos.
    
    Args:
        text: Texto a ser sanitizado (ex: "Dia de Chuva & Melancolia")
        
    Returns:
        Texto limpo para uso como filename (ex: "dia_de_chuva_melancolia")
    """
    # Converte para minúsculas
    text = text.lower()
    
    # Remove acentos básicos
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u',
        'ç': 'c'
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Substitui espaços e caracteres especiais por underscore
    # Mantém apenas letras, números e underscores
    text = re.sub(r'[^a-z0-9_\s]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'_+', '_', text)
    
    # Remove underscores nas extremidades
    text = text.strip('_')
    
    return text if text else "playlist"


def _generate_timestamp_suffix() -> str:
    """
    Gera um sufixo de timestamp para evitar colisões de nomes.
    
    Returns:
        String no formato YYYYMMDD_HHMMSS (ex: "20260610_143022")
    """
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ========== LÓGICA PRINCIPAL ==========

def save_playlist(
    music_file_paths: List[str],
    playlist_name: str
) -> str:
    """
    Salva uma lista de caminhos de música em um arquivo .m3u8 usando caminhos relativos.
    """
    if not music_file_paths:
        raise ValueError("Lista de músicas não pode estar vazia")
    
    if not isinstance(music_file_paths, list):
        raise TypeError("music_file_paths deve ser uma lista")
    
    # 1. Garante que o diretório existe (Certifique-se que esta func aponta para /MusicPlex)
    playlist_folder = _ensure_playlist_folder_exists()
    
    # 2. Sanitiza o nome da playlist
    clean_name = _sanitize_filename(playlist_name)
    timestamp = _generate_timestamp_suffix()
    
    # 3. Monta o nome do arquivo
    filename = f"ia_playlist_{clean_name}_{timestamp}.m3u8"
    filepath = os.path.join(playlist_folder, filename)
    
    # 4. Valida que não há duplicatas de caminho
    unique_paths = list(set(music_file_paths))
    if len(unique_paths) < len(music_file_paths):
        logger.warning(
            f"Removidas {len(music_file_paths) - len(unique_paths)} músicas duplicadas"
        )
        music_file_paths = unique_paths
    
    # =====================================================================
    # 4.5 CONVERSÃO PARA CAMINHOS RELATIVOS (UNIVERSAIS)
    # =====================================================================
    relative_paths = []
    for plex_path in music_file_paths:
        # Troca a base do Plex pela do Backend
        backend_path = plex_path.replace("/Musicaa", "/MusicPlex")
        
        # Calcula o caminho relativo a partir da pasta onde o .m3u8 será salvo
        rel_path = os.path.relpath(backend_path, start=playlist_folder)
        
        # Garante barras no padrão m3u8 (/) mesmo rodando em Windows/Linux
        rel_path = rel_path.replace("\\", "/")
        relative_paths.append(rel_path)
    # =====================================================================

    # 5. Cria o conteúdo do arquivo M3U8 usando a NOVA lista de caminhos relativos
    m3u8_content = _generate_m3u8_content(relative_paths)
    
    # 6. Salva o arquivo
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(m3u8_content)
        
        logger.info(
            f"Playlist salva com sucesso: {filepath} "
            f"({len(relative_paths)} músicas)"
        )
        
        return filepath
        
    except IOError as e:
        raise IOError(f"Erro ao salvar playlist {filepath}: {e}")
    except Exception as e:
        raise Exception(f"Erro inesperado ao salvar playlist: {e}")


def _generate_m3u8_content(music_file_paths: List[str]) -> str:
    """
    Gera o conteúdo formatado de um arquivo .m3u8.
    
    Formato:
    #EXTM3U
    #EXTINF:-1, Título da Música
    /caminho/para/arquivo.mp3
    
    Args:
        music_file_paths: Lista de caminhos absolutos
        
    Returns:
        String contendo o conteúdo completo do arquivo .m3u8
    """
    lines = ["#EXTM3U"]
    
    for file_path in music_file_paths:
        # Extrai o nome do arquivo para usar como título
        filename = os.path.basename(file_path)
        # Remove a extensão do arquivo
        title = os.path.splitext(filename)[0]
        
        # Adiciona a entrada EXTINF
        lines.append(f"#EXTINF:-1, {title}")
        # Adiciona o caminho do arquivo
        lines.append(file_path)
    
    # Junta com quebras de linha e garante uma quebra ao final
    return "\n".join(lines) + "\n"


# ========== UTILITÁRIOS ==========

def list_existing_playlists() -> List[str]:
    """
    Lista todas as playlists existentes no diretório.
    
    Returns:
        Lista de nomes de arquivos .m3u8
    """
    try:
        playlist_folder = _ensure_playlist_folder_exists()
        playlists = [
            f for f in os.listdir(playlist_folder)
            if f.endswith('.m3u8')
        ]
        logger.info(f"Encontradas {len(playlists)} playlists existentes")
        return sorted(playlists)
    except Exception as e:
        logger.error(f"Erro ao listar playlists: {e}")
        return []


def delete_playlist(filename: str) -> bool:
    """
    Deleta uma playlist pelo nome do arquivo.
    
    Args:
        filename: Nome do arquivo (ex: "ia_playlist_dia_de_chuva_20260610_143022.m3u8")
        
    Returns:
        True se deletado com sucesso, False caso contrário
    """
    try:
        playlist_folder = _ensure_playlist_folder_exists()
        filepath = os.path.join(playlist_folder, filename)
        
        # Valida que o arquivo está dentro do diretório permitido
        if not os.path.abspath(filepath).startswith(os.path.abspath(playlist_folder)):
            raise PermissionError(f"Acesso negado ao arquivo: {filename}")
        
        if os.path.exists(filepath) and filepath.endswith('.m3u8'):
            os.remove(filepath)
            logger.info(f"Playlist deletada: {filename}")
            return True
        else:
            logger.warning(f"Arquivo não encontrado ou inválido: {filename}")
            return False
            
    except Exception as e:
        logger.error(f"Erro ao deletar playlist {filename}: {e}")
        return False


def get_playlist_info(filename: str) -> dict:
    """
    Retorna informações sobre uma playlist específica.
    
    Args:
        filename: Nome do arquivo da playlist
        
    Returns:
        Dicionário com informações: path, size, tracks_count, created_time
    """
    try:
        playlist_folder = _ensure_playlist_folder_exists()
        filepath = os.path.join(playlist_folder, filename)
        
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Playlist não encontrada: {filename}")
        
        # Conta o número de tracks (linhas com #EXTINF)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            track_count = content.count('#EXTINF:')
        
        file_stat = os.stat(filepath)
        
        return {
            "filename": filename,
            "path": filepath,
            "size_bytes": file_stat.st_size,
            "track_count": track_count,
            "created_time": datetime.fromtimestamp(file_stat.st_ctime).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter informações da playlist: {e}")
        return {}
