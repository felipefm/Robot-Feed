import requests
from bs4 import BeautifulSoup
from typing import Dict, Any
import re
from datetime import datetime, timezone
import os
import yt_dlp
from urllib.parse import urlparse, parse_qs
import subprocess  # <-- ADICIONE ESTA LINHA

from app.core.transcript_client import fetch_transcript

def get_channel_details(channel_identifier: str) -> Dict[str, Any] | None:
    """
    Busca os detalhes de um canal (ID e Título) fazendo scraping da página principal do YouTube.

    Args:
        channel_identifier: O ID do canal (ex: "UC_x5XG1OV2P6uZZ5FSM9Ttw") ou o handle (ex: "@Google").

    Returns:
        Um dicionário com "id" e "title" do canal, ou None se não for encontrado.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # --- Tentar como Twitch ---
    twitch_username = None
    # Verifica se é uma URL do Twitch
    twitch_url_match = re.match(r'(?:https?:\/\/)?(?:www\.)?twitch\.tv\/([a-zA-Z0-9_]+)', channel_identifier)
    if twitch_url_match:
        twitch_username = twitch_url_match.group(1)
    # Se não for URL do Twitch e não parecer um ID/handle do YouTube, assume que pode ser um nome de usuário do Twitch
    elif not channel_identifier.startswith(('UC', '@', 'https://www.youtube.com/', 'https://youtu.be/')):
        twitch_username = channel_identifier.strip()

    if twitch_username:
        twitch_check_url = f"https://www.twitch.tv/{twitch_username}"
        try:
            # Faz uma requisição HEAD para verificar a existência sem baixar o conteúdo completo
            response = requests.head(twitch_check_url, headers=headers, timeout=5)
            response.raise_for_status() # Levanta exceção para 4xx/5xx
            # Se chegou aqui, o canal provavelmente existe.
            # Não há uma API fácil para obter o "título" de um canal Twitch via scraping simples sem JS.
            # Usamos o username como título por enquanto.
            return {"id": f"twitch:{twitch_username}", "title": twitch_username, "platform": "twitch"}
        except requests.exceptions.RequestException:
            # Não é um canal Twitch válido ou erro de rede, continua para a verificação do YouTube
            pass

    # --- Tentar como YouTube ---
    youtube_target_url = None
    if channel_identifier.startswith('UC'):
        youtube_target_url = f"https://www.youtube.com/channel/{channel_identifier}"
    elif channel_identifier.startswith('@'):
        youtube_target_url = f"https://www.youtube.com/{channel_identifier}"
    elif "youtube.com/channel/" in channel_identifier or "youtube.com/@" in channel_identifier:
        youtube_target_url = channel_identifier

    if not youtube_target_url:
        return None # Não é YouTube nem Twitch reconhecido

    # O YouTube redireciona handles para a URL com ID, então podemos usar a mesma base
    try:
        response = requests.get(youtube_target_url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        
        title_tag = soup.find("meta", property="og:title")
        url_tag = soup.find("meta", property="og:url")

        if title_tag and url_tag:
            title = title_tag["content"]
            channel_id = url_tag["content"].split("/")[-1]
            if channel_id.startswith("UC"): # Garante que é um ID de canal válido
                return {"id": channel_id, "title": title}

    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar detalhes do canal {channel_identifier}: {e}")
        return None
    
    return None


def is_channel_live(channel_identifier: str) -> tuple[bool, str | None]:
    """
    Verifica se um canal do YouTube está em live fazendo scraping da página /live.
    A própria página /live já traz o player do vídeo (videoDetails e playabilityStatus),
    então não é preciso abrir a página /watch (que passou a retornar 429 para o backend).

    Args:
        channel_identifier: O ID do canal (ex: "UC-lHJZR3Gqxm24_Vd_AJ5Yw") ou o handle (ex: "LofiGirl").

    Returns:
        Uma tupla (True, video_id) se o canal estiver ao vivo, (False, None) caso contrário.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # --- Etapa 1: Encontrar a URL do vídeo da live ---
    # Garante que não teremos um '@' duplicado na URL se o handle for passado com ele
    handle = channel_identifier.lstrip('@')
    if channel_identifier.startswith('UC'):
        live_page_url = f"https://www.youtube.com/channel/{channel_identifier}/live"
    else:
        live_page_url = f"https://www.youtube.com/@{handle}/live"

    video_url = None
    try:
        response = requests.get(live_page_url, headers=headers, timeout=10, allow_redirects=True)
        response.raise_for_status()
        html = response.text

        soup = BeautifulSoup(html, "html.parser")

        canonical_link = soup.find("link", {"rel": "canonical"})
        if canonical_link and canonical_link.get("href") and "watch?v=" in canonical_link.get("href"):
            video_url = canonical_link.get("href")

    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar página /live (Canal: {channel_identifier}): {e}")
        return False, None

    if not video_url:
        return False, None

    # --- Etapa 2: Verificar na própria página /live se o vídeo está ao vivo agora ---
    # Live agendada também tem "isLive":true, mas vem com "isUpcoming":true
    # e playabilityStatus LIVE_STREAM_OFFLINE. Live em andamento tem status OK.
    playability = re.search(r'"playabilityStatus":\{"status":"(\w+)"', html)
    if ('"isLive":true' in html
            and '"isUpcoming":true' not in html
            and playability and playability.group(1) == "OK"):
        video_id = video_url.split('v=')[-1].split('&')[0]
        return True, video_id

    return False, None

def get_live_stream_duration(video_identifier: str) -> Dict[str, Any] | None:
    """
    Obtém a duração de uma live stream ativa (tempo decorrido desde o início).

    Args:
        video_identifier: A URL do vídeo (ex: "https://www.youtube.com/watch?v=...") ou o ID do vídeo.

    Returns:
        Um dicionário com 'start_time', 'duration_str' e 'duration_seconds', ou None se falhar.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    # Extrair ID se for uma URL completa
    video_id = video_identifier
    if "v=" in video_identifier:
        video_id = video_identifier.split("v=")[-1].split("&")[0]
    elif "youtu.be/" in video_identifier:
        video_id = video_identifier.split("youtu.be/")[-1].split("?")[0]

    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # O YouTube geralmente coloca a data de início no HTML dentro de itemprop="startDate"
        # ou dentro do JSON de configuração. O método mais robusto via scraping simples é o meta tag ou regex no JSON.
        
        # Tenta encontrar via Regex no JSON (mais comum para dados precisos de lives agendadas ou passadas)
        # Procura por "startDate":"2023-10-27T14:00:00-03:00"
        start_date_match = re.search(r'"startDate":"(.*?)"', response.text)
        
        # Fallback: Tenta encontrar "startTimestamp" (comum em lives ativas)
        if not start_date_match:
            start_date_match = re.search(r'"startTimestamp":"(.*?)"', response.text)
        
        if start_date_match:
            start_time_str = start_date_match.group(1)
            # Correção para formato ISO com 'Z' (UTC) que o Python < 3.11 pode não aceitar nativamente
            if start_time_str.endswith('Z'):
                start_time_str = start_time_str.replace('Z', '+00:00')
            # Converte string ISO 8601 para objeto datetime
            start_time = datetime.fromisoformat(start_time_str)
            now = datetime.now(start_time.tzinfo) # Usa o mesmo timezone da resposta
            duration = now - start_time
            
            return {
                "video_id": video_id,
                "start_time": start_time_str,
                "duration_seconds": int(duration.total_seconds()),
                "duration_str": str(duration).split('.')[0] # Remove milissegundos para ficar bonito (H:MM:SS)
            }
            
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"Erro ao buscar duração da live {video_id}: {e}")
        return None
    
    return None

def parse_time_to_seconds(time_str: str) -> int:
    """Converte 'MM:SS' ou 'HH:MM:SS' em segundos totais."""
    parts = list(map(int, time_str.split(':')))
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    elif len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return int(parts[0])

def extract_video_id(url: str) -> str:
    """Extrai o ID do vídeo de uma URL do YouTube."""
    parsed_url = urlparse(url)
    
    if parsed_url.hostname in ('youtu.be', 'www.youtu.be'):
        return parsed_url.path[1:]
        
    if parsed_url.hostname in ('youtube.com', 'www.youtube.com'):
        if parsed_url.path == '/watch':
            query = parse_qs(parsed_url.query)
            if 'v' in query:
                return query['v'][0]
        # Adicionada verificação para /live/, /shorts/ e /embed/
        elif parsed_url.path.startswith(('/live/', '/shorts/', '/embed/')):
            return parsed_url.path.split('/')[2]
            
    return url # Retorna a string pura se não cair nas regras (pode já ser o ID)

def process_youtube_clip(url: str, start_time: str, end_time: str, output_dir: str = "./downloads"):
    """
    Baixa o trecho do vídeo e extrai a transcrição correspondente.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    video_id = extract_video_id(url)
    start_sec = parse_time_to_seconds(start_time)
    end_sec = parse_time_to_seconds(end_time)

    video_filename = os.path.join(output_dir, f"{video_id}_{start_sec}_to_{end_sec}.mp4")
    
    # 1. RECORTAR O VÍDEO USANDO O MODO "NATIVO" E ARQUIVO ÚNICO (720p)
    comando_ytdlp = [
        "yt-dlp",
        # O pulo do gato final: Forçamos o arquivo único (best) que não dessincroniza
        "-f", "best[ext=mp4]/best",
        "--download-sections", f"*{start_sec}-{end_sec}",
        "-o", video_filename,
        "--quiet",
        url
    ]
    
    try:
        # Executa o comando no terminal do container de forma segura
        subprocess.run(comando_ytdlp, check=True)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Erro ao baixar o vídeo via subprocess yt-dlp: {e}")

    # 2. RECORTAR A TRANSCRIÇÃO
    text_clip = []
    try:
        transcript = fetch_transcript(video_id, languages=['pt', 'en'])

        for entry in transcript:
            entry_start = entry.start
            entry_end = entry_start + entry.duration

            if entry_start <= end_sec and entry_end >= start_sec:
                text_clip.append(entry.text)

    except Exception:
        text_clip.append("[Não foi possível extrair a transcrição para este trecho]")

    texto_final = "\n".join(text_clip)
    
    txt_filename = os.path.join(output_dir, f"{video_id}_{start_sec}_to_{end_sec}.txt")
    with open(txt_filename, "w", encoding="utf-8") as f:
        f.write(texto_final)

    return {
        "video_path": video_filename,
        "txt_path": txt_filename,
        "transcript_preview": texto_final[:500] + "..." if len(texto_final) > 500 else texto_final
    }


if __name__ == '__main__':
    import asyncio
    # --- Testes ---
    def safe_print(s):
        # Adiciona um prefixo para distinguir a saída do teste
        s = f"[TEST] {s}"
        try:
            print(s)
        except UnicodeEncodeError:
            print(s.encode('utf-8').decode('cp1252', 'ignore'))

    # -- Teste da nova função get_channel_details --
    safe_print("--- Testando get_channel_details ---")
    safe_print(f"Detalhes para '@LofiGirl': {get_channel_details('@LofiGirl')}")
    safe_print(f"Detalhes para 'UC_x5XG1OV2P6uZZ5FSM9Ttw' (Google): {get_channel_details('UC_x5XG1OV2P6uZZ5FSM9Ttw')}")
    safe_print(f"Detalhes para 'gaules' (Twitch): {get_channel_details('gaules')}")
    safe_print(f"Detalhes para 'nonexistentchannel123456': {get_channel_details('nonexistentchannel123456')}\n")

    # -- Testes da função is_channel_live --
    safe_print("--- Testando is_channel_live ---")
    live_channel_handle = "LofiGirl"
    safe_print(f"Verificando o canal por handle: {live_channel_handle}")
    is_live_handle, video_id_handle = is_channel_live(live_channel_handle)
    result_live_handle = 'Sim' if is_live_handle else 'Não'
    safe_print(f"O canal '{live_channel_handle}' está ao vivo? {result_live_handle} (ID do vídeo: {video_id_handle})\n")

    live_channel_id = "UC-lHJZR3Gqxm24_Vd_AJ5Yw" # ID do canal Lofi Girl
    safe_print(f"Verificando o canal por ID: {live_channel_id}")
    is_live_id, video_id_id = is_channel_live(live_channel_id)
    result_live_id = 'Sim' if is_live_id else 'Não'
    safe_print(f"O canal '{live_channel_id}' está ao vivo? {result_live_id} (ID do vídeo: {video_id_id})\n")
    
    offline_channel_handle = "google"
    safe_print(f"Verificando o canal offline: {offline_channel_handle}")
    is_live_offline, video_id_offline = is_channel_live(offline_channel_handle)
    result_offline = 'Sim' if is_live_offline else 'Não'
    safe_print(f"O canal '{offline_channel_handle}' está ao vivo? {result_offline}")

    # -- Teste de duração --
    # Nota: Para testar isso, você precisa de um ID de vídeo que esteja ao vivo ou que foi uma live recente.
    # safe_print("--- Testando get_live_stream_duration ---")
    # safe_print(get_live_stream_duration("https://www.youtube.com/watch?v=VIDEO_ID_AQUI"))


