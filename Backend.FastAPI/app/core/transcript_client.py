"""
Cliente central para extração de transcrições do YouTube.

Concentra a configuração de proxy (contorno para bloqueio de IP pelo YouTube -
RequestBlocked/IpBlocked) e o espaçamento mínimo entre requisições, para que
todo ponto do backend que precise de transcrição (summarizer, clips, etc.)
passe pelo mesmo caminho.

Nota sobre cookies: a autenticação via cookies é uma opção nativa da lib, mas
está desativada no momento pelo próprio mantenedor (mudanças recentes da API
do YouTube quebraram essa implementação - ver CookieError/AgeRestricted em
youtube_transcript_api._errors). Por isso o único contorno viável hoje é proxy.
"""

import os
import threading
import time
import logging
from typing import Iterable, Optional

from youtube_transcript_api import YouTubeTranscriptApi, FetchedTranscript
from youtube_transcript_api.proxies import (
    ProxyConfig,
    GenericProxyConfig,
    WebshareProxyConfig,
)

logger = logging.getLogger(__name__)


def _build_proxy_config() -> Optional[ProxyConfig]:
    webshare_username = os.getenv("WEBSHARE_PROXY_USERNAME")
    webshare_password = os.getenv("WEBSHARE_PROXY_PASSWORD")
    if webshare_username and webshare_password:
        locations_raw = os.getenv("WEBSHARE_PROXY_LOCATIONS", "")
        filter_ip_locations = [
            loc.strip() for loc in locations_raw.split(",") if loc.strip()
        ] or None
        logger.info(
            "Transcrições do YouTube serão obtidas via proxy residencial Webshare."
        )
        return WebshareProxyConfig(
            proxy_username=webshare_username,
            proxy_password=webshare_password,
            filter_ip_locations=filter_ip_locations,
        )

    http_url = os.getenv("YTT_PROXY_HTTP_URL")
    https_url = os.getenv("YTT_PROXY_HTTPS_URL")
    if http_url or https_url:
        logger.info(
            "Transcrições do YouTube serão obtidas via proxy genérico configurado."
        )
        return GenericProxyConfig(http_url=http_url, https_url=https_url)

    logger.warning(
        "Nenhum proxy configurado para youtube-transcript-api (defina "
        "WEBSHARE_PROXY_USERNAME/PASSWORD ou YTT_PROXY_HTTP_URL/YTT_PROXY_HTTPS_URL). "
        "As requisições sairão pelo IP local e podem continuar sendo bloqueadas pelo YouTube."
    )
    return None


_PROXY_CONFIG = _build_proxy_config()

# Espaçamento mínimo entre requisições de transcrição, mesmo para chamadas
# manuais que não passam pela fila do Flask (que já processa 1 vídeo/5min).
# Existe para evitar repetir a rajada (19 vídeos em ~4min) que motivou o
# bloqueio de IP anterior.
_MIN_INTERVAL_SECONDS = float(os.getenv("YTT_MIN_INTERVAL_SECONDS", "5"))
_rate_lock = threading.Lock()
_last_call_at = 0.0


def _throttle() -> None:
    global _last_call_at
    with _rate_lock:
        wait = _MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


def fetch_transcript(
    video_id: str, languages: Iterable[str] = ("en",)
) -> FetchedTranscript:
    """
    Busca a transcrição de um vídeo, aplicando o proxy configurado (se houver)
    e o espaçamento mínimo entre requisições.

    Uma instância nova de YouTubeTranscriptApi é criada a cada chamada porque a
    lib não é thread-safe (cada instância mantém sua própria requests.Session),
    já que o backend usa run_in_threadpool. A config de proxy é reaproveitada
    entre chamadas por ser imutável.
    """
    _throttle()
    api = YouTubeTranscriptApi(proxy_config=_PROXY_CONFIG)
    return api.fetch(video_id, languages=list(languages))
