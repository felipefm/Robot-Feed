"""
feed_service.py - Serviço de verificação de feeds do YouTube
Núcleo da lógica de monitoramento de canais
"""

import html
import logging
import time
import requests
import feedparser
from datetime import datetime, timedelta
from models import Channel, get_config
from telegram_bot import send_telegram_message, check_mute_transition, process_notification_queue, youtube_thumbnail_candidates
from extensions import db

logger = logging.getLogger(__name__)

# Variável global para controlar o progresso da verificação
check_progress = {'current': 0, 'total': 0, 'status': 'idle', 'running': False}
last_check_time = None


def get_last_check_time():
    """Retorna a última vez que a verificação foi realizada"""
    return last_check_time


# O RSS do YouTube às vezes responde 404 por instabilidade: só marca o canal como
# indisponível depois de tantas verificações seguidas com 404
RSS_NOT_FOUND_LIMIT = 3


def register_rss_not_found(channel):
    """Conta um 404 do RSS e, ao atingir o limite, marca o canal como indisponível e avisa uma vez"""
    channel.rss_not_found_count = (channel.rss_not_found_count or 0) + 1
    logger.warning(f"RSS não encontrado ({channel.rss_not_found_count}/{RSS_NOT_FOUND_LIMIT}) para: {channel.name}")

    if channel.rss_not_found_count >= RSS_NOT_FOUND_LIMIT and not channel.unavailable_since:
        channel.unavailable_since = datetime.now()
        logger.warning(f"CANAL INDISPONÍVEL: {channel.name} ({channel.channel_id})")
        if not channel.mute_notifications:
            send_telegram_message(f"⚠️ <b>Canal indisponível: {html.escape(channel.name, quote=False)}</b>\n\n"
                                  f"O YouTube não encontra mais este canal (removido, encerrado ou ID alterado).\n"
                                  f"🔗 https://www.youtube.com/channel/{channel.channel_id}")
    db.session.commit()


def channel_page_exists(channel_id):
    """Confirma pela página do canal se ele ainda existe.
    True = existe; False = não existe; None = inconclusivo (bloqueio, erro de rede ou página inesperada).
    Canal inexistente também responde 200, por isso a resposta é decidida pelo conteúdo."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9",
    }
    try:
        resp = requests.get(f"https://www.youtube.com/channel/{channel_id}", headers=headers, timeout=15)
    except Exception as e:
        logger.debug(f"Página do canal {channel_id} inacessível: {e}")
        return None

    if resp.status_code == 404:
        return False
    # 429, redirecionamento para captcha (google.com/sorry) ou consentimento: não dá para concluir nada
    if resp.status_code != 200 or 'youtube.com' not in resp.url or 'ytInitialData' not in resp.text:
        logger.debug(f"Página do canal {channel_id} inconclusiva (HTTP {resp.status_code}, {resp.url})")
        return None
    return 'channelMetadataRenderer' in resp.text


# Mais da metade dos canais com 404 na mesma rodada = instabilidade do YouTube, não canais removidos
RSS_OUTAGE_RATIO = 0.5
# Limite de páginas de canal abertas por rodada, para não chamar atenção do YouTube (bloqueio de IP)
MAX_PAGE_CONFIRMATIONS = 5


def evaluate_rss_not_found(suspects, total_channels):
    """Decide, ao fim da rodada, quais 404 do RSS contam para marcar canal como indisponível"""
    if not suspects:
        return

    if len(suspects) > total_channels * RSS_OUTAGE_RATIO:
        logger.warning(f"Instabilidade do YouTube: RSS deu 404 para {len(suspects)}/{total_channels} canais "
                       f"nesta rodada. Nenhum 404 foi contado.")
        return

    pages_opened = 0
    for channel in suspects:
        # Já confirmado em rodadas anteriores: não precisa abrir a página de novo
        if channel.unavailable_since:
            register_rss_not_found(channel)
            continue

        if pages_opened >= MAX_PAGE_CONFIRMATIONS:
            logger.info(f"Limite de {MAX_PAGE_CONFIRMATIONS} confirmações por rodada atingido. "
                        f"404 de {channel.name} não foi contado (será reavaliado na próxima rodada).")
            continue

        if pages_opened:
            time.sleep(2)  # Espaça os acessos ao YouTube
        pages_opened += 1

        exists = channel_page_exists(channel.channel_id)
        if exists is False:
            register_rss_not_found(channel)
        elif exists is True:
            logger.info(f"RSS deu 404, mas a página do canal existe: {channel.name}. 404 ignorado.")
        else:
            logger.info(f"RSS deu 404 e a página do canal não pôde ser confirmada: {channel.name}. 404 não contado.")


def register_rss_found(channel):
    """Zera o contador de 404 e, se o canal estava indisponível, registra que ele voltou"""
    if channel.unavailable_since:
        logger.info(f"Canal voltou a responder: {channel.name}")
        if not channel.mute_notifications:
            send_telegram_message(f"✅ <b>Canal disponível novamente: {html.escape(channel.name, quote=False)}</b>")
    channel.rss_not_found_count = 0
    channel.unavailable_since = None
    db.session.commit()


# IDs já notificados por canal: evita avisar de novo uma live agendada/estreia que
# volta ao topo do RSS quando acontece (o YouTube atualiza a data de publicação)
NOTIFIED_HISTORY_SIZE = 30


def notified_ids(channel):
    return (channel.notified_video_ids or '').split()


def remember_notified(channel, video_id):
    """Coloca o ID no topo do histórico de notificados (sem commit)"""
    if not video_id:
        return
    ids = [video_id] + [i for i in notified_ids(channel) if i != video_id]
    channel.notified_video_ids = ' '.join(ids[:NOTIFIED_HISTORY_SIZE])


def seed_notified_ids(channel, entries):
    """Primeira execução do canal com o histórico vazio: considera notificado o que o sistema
    já tinha visto (a última live e os vídeos do RSS a partir do last_video_id para baixo)"""
    seed = []
    if channel.last_live_id:
        seed.append(channel.last_live_id)
    feed_ids = [getattr(e, 'yt_videoid', None) for e in entries]
    if channel.last_video_id in feed_ids:
        seed += feed_ids[feed_ids.index(channel.last_video_id):]
    elif channel.last_video_id:
        seed.append(channel.last_video_id)
    seed = [i for i in dict.fromkeys(seed) if i]
    channel.notified_video_ids = ' '.join(seed[:NOTIFIED_HISTORY_SIZE])
    db.session.commit()


def check_feeds():
    """Tarefa agendada para verificar novos vídeos"""
    global check_progress, last_check_time
    
    try:
        # Verifica transição de Mute antes de iniciar a varredura
        check_mute_transition()
        
        logger.info("--- Iniciando verificação de feeds ---")
        check_progress['running'] = True
        check_progress['status'] = 'Iniciando...'
        check_progress['current'] = 0
        check_progress['total'] = 0

        # Prepara URL da API
        conf = get_config()
        
        # Diagnóstico de Configuração
        mute_info = f"Mute: {conf.mute_start_hour}h-{conf.mute_end_hour}h" if conf.mute_start_hour != -1 else "Mute: OFF"
        logger.debug(f"Configuração: Telegram {'ATIVO' if conf.telegram_token and conf.telegram_chat_id else 'INATIVO'} | Intervalo: {conf.check_interval_minutes} min | Cooldown: {conf.live_cooldown_minutes} min | {mute_info} | API: {conf.youtube_api_url}")

        api_url = conf.youtube_api_url or "http://host.docker.internal:8000"
        if api_url.endswith('/'): api_url = api_url[:-1]

        channels = Channel.query.all()
        
        if not channels:
            check_progress['status'] = 'Sem canais'
            logger.info("Nenhum canal cadastrado para verificar.")
            return

        check_progress['total'] = len(channels)

        # Canais cujo RSS deu 404 nesta rodada (avaliados só no fim, todos juntos)
        rss_404_suspects = []

        # --- Função Interna de Verificação (Encapsulada para Reuso) ---
        def verify_channel_logic(channel):
            # 1. Tenta verificar LIVE pela API Backend (Prioridade)
            try:
                # Usa o endpoint de checagem individual que você forneceu
                live_response = requests.get(f"{api_url}/api/check-live/{channel.channel_id}", timeout=5)
                
                if live_response.status_code == 200:
                    live_data = live_response.json()
                    
                    # Se a API confirmar que está ao vivo
                    if live_data.get('is_live') is True:
                        channel.is_live = True
                        video_id = live_data.get('video_id')
                        
                        video_link = f"https://www.youtube.com/watch?v={video_id}"
                        channel.last_live_thumb = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"

                        # Lógica de Notificação Inteligente
                        should_notify = False
                        
                        # Caso 1: É uma live totalmente nova (ID diferente do último salvo)
                        if video_id and channel.last_live_id != video_id:
                            should_notify = True
                            channel.muted_live_id = None # Reseta o silêncio, pois é uma nova live
                            logger.info(f"LIVE NOVA DETECTADA: {channel.name}")
                        
                        # Caso 2: É a mesma live, mas verificamos se o tempo de espera (cooldown) já passou
                        elif video_id and channel.last_live_id == video_id:
                            cooldown = conf.live_cooldown_minutes or 120
                            if channel.last_live_notify:
                                time_since_last = datetime.now() - channel.last_live_notify
                                if time_since_last > timedelta(minutes=cooldown):
                                    should_notify = True
                                    logger.info(f"LEMBRETE DE LIVE (Cooldown {cooldown}m passou): {channel.name}")
                        
                        if should_notify:
                            msg = (f"🔴 <b>ESTÁ AO VIVO: {html.escape(channel.name, quote=False)}</b>\n\n"
                                   f"🔗 {video_link}")
                            
                            # Verifica se há Mute Global OU se esta Live específica foi silenciada
                            is_live_muted = (channel.muted_live_id == video_id)
                            if not channel.mute_notifications and not is_live_muted:
                                send_telegram_message(msg, photo_urls=youtube_thumbnail_candidates(video_id, live=True),
                                                      button_url=video_link)
                            else:
                                logger.info(f"Notificação de LIVE silenciada ({'Global' if channel.mute_notifications else 'Específica'}) para: {channel.name}")
                            
                            channel.last_live_id = video_id
                            channel.last_live_notify = datetime.now() # Atualiza o relógio do cooldown
                            remember_notified(channel, video_id)
                        
                        db.session.commit()
                    else:
                        # Se não está ao vivo, garante que o status reflete isso
                        if channel.is_live:
                            channel.is_live = False
                            channel.muted_live_id = None # Limpa o silêncio pois a live acabou
                            db.session.commit()
            
            except Exception as e:
                # Se a API falhar, lança exceção para ser capturada pelo sistema de retry
                raise Exception(f"API Live Error: {e}")

            # 2. Verificação de Uploads via RSS (Padrão)
            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel.channel_id}"
            try:
                feed = feedparser.parse(rss_url)

                # Canal removido/encerrado: o RSS responde 404. Só vira suspeito; a decisão
                # sai no fim da rodada (evaluate_rss_not_found). Sem retry, para não contar várias vezes.
                if feed.get('status') == 404:
                    if channel not in rss_404_suspects:
                        rss_404_suspects.append(channel)
                    return True
                if channel.rss_not_found_count or channel.unavailable_since:
                    register_rss_found(channel)

                if feed.entries:
                    if channel.notified_video_ids is None:
                        seed_notified_ids(channel, feed.entries)

                    # --- LÓGICA DE DETECÇÃO DE MÚLTIPLOS VÍDEOS ---
                    new_videos = []
                    found_last_seen = False
                    
                    # Se o canal é novo (sem ID salvo), pegamos apenas o último para evitar spam
                    if channel.last_video_id is None:
                         new_videos = [feed.entries[0]]
                         found_last_seen = True 
                    else:
                        # Percorre a lista procurando onde paramos da última vez
                        for entry in feed.entries:
                            if getattr(entry, 'yt_videoid', None) == channel.last_video_id:
                                found_last_seen = True
                                break
                            new_videos.append(entry)
                    
                    # Proteção: Se não achou o último vídeo (ex: muito antigo), 
                    # ou se a lista de novos for gigante, notifica apenas o mais recente para evitar spam massivo.
                    if not found_last_seen and len(new_videos) > 5:
                        logger.warning(f"Muitos vídeos novos ou perda de sincronia para {channel.name}. Notificando apenas o último.")
                        new_videos = [feed.entries[0]]

                    # Processa os vídeos novos (Invertemos a lista para notificar do Antigo -> Novo)
                    if new_videos:
                        for entry in reversed(new_videos):
                            video_id = getattr(entry, 'yt_videoid', None)
                            video_title = getattr(entry, 'title', 'Sem título')
                            # Usa sempre watch?v= (inclusive para Shorts, cujo link /shorts/ gera preview pouco confiável no Telegram)
                            video_link = f'https://www.youtube.com/watch?v={video_id}' if video_id else getattr(entry, 'link', '')
                            video_published = getattr(entry, 'published', None)
                            # media:thumbnail do feed (feedparser expõe como lista de dicts)
                            feed_thumb = (getattr(entry, 'media_thumbnail', None) or [{}])[0].get('url')
                            
                            # Evita notificar o vídeo se ele for a própria Live que já está rolando (ou acabou de acabar)
                            if video_id == channel.last_live_id:
                                channel.last_video_id = video_id
                                db.session.commit()
                                continue

                            video_thumb = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"

                            # Já notificado antes (ex: live agendada/estreia que voltou ao topo do RSS ao acontecer)
                            if video_id in notified_ids(channel):
                                logger.info(f"Vídeo já notificado antes, ignorando: {channel.name} - {video_title} ({video_id})")
                                channel.last_video_id = video_id
                                channel.last_video_thumb = video_thumb
                                channel.last_video_published = video_published
                                db.session.commit()
                                continue

                            logger.info(f"NOVO VÍDEO DETECTADO: {channel.name} - {video_title}")

                            msg = (f"🚨 <b>Novidade no Canal: {html.escape(channel.name, quote=False)}</b>\n\n"
                                   f"📺 {html.escape(video_title, quote=False)}\n"
                                   f"🔗 {video_link}")
                            
                            if not channel.mute_notifications:
                                send_telegram_message(msg, photo_urls=youtube_thumbnail_candidates(video_id, feed_thumb),
                                                      button_url=video_link)
                            else:
                                logger.info(f"Notificação de VÍDEO silenciada para: {channel.name}")
                            
                            # Atualiza o banco passo a passo (garante que se falhar no meio, o que foi enviado fica salvo)
                            channel.last_video_id = video_id
                            channel.last_video_thumb = video_thumb
                            channel.last_video_published = video_published
                            remember_notified(channel, video_id)
                            db.session.commit()
                    
                    # Se não tem vídeos novos, mas queremos atualizar metadados do último (caso falte)
                    elif not new_videos and feed.entries:
                        latest_entry = feed.entries[0]
                        video_id = getattr(latest_entry, 'yt_videoid', None)
                        
                        if video_id == channel.last_video_id:
                            missing_data = (not channel.last_video_thumb or
                                          not channel.last_video_published)

                            if missing_data:
                                # Recoleta dados para atualização visual (tudo vem do próprio RSS)
                                channel.last_video_thumb = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                                channel.last_video_published = getattr(latest_entry, 'published', None)
                                db.session.commit()

                return True # Sucesso RSS

            except Exception as e:
                raise Exception(f"RSS Error: {e}")

        # --- Execução com Fila de Retry (A Lógica de Fila) ---
        failed_channels = []

        # 1. Primeira Passada (Tenta todos)
        for channel in channels:
            try:
                verify_channel_logic(channel)
                check_progress['current'] += 1
            except Exception as e:
                logger.warning(f"Tentativa 1 falhou para {channel.name}: {e}")
                failed_channels.append(channel)

        # 2. Retries (3x) - Volta apenas nos que falharam
        for attempt in range(1, 4):
            if not failed_channels:
                break
            
            logger.info(f"--- Iniciando Retry {attempt}/3 para {len(failed_channels)} canais com falha ---")
            next_failed = []
            
            for channel in failed_channels:
                try:
                    verify_channel_logic(channel)
                    check_progress['current'] += 1 # Sucesso no retry, atualiza progresso
                    logger.info(f"Sucesso no retry para {channel.name}")
                except Exception as e:
                    logger.warning(f"Retry {attempt} falhou para {channel.name}: {e}")
                    next_failed.append(channel)
            
            failed_channels = next_failed

        # 3. Registro Final de Falhas
        for channel in failed_channels:
            logger.error(f"FALHA DEFINITIVA: Não foi possível verificar {channel.name} após todas as tentativas.")
            check_progress['current'] += 1 # Incrementa para finalizar a barra de progresso

        # 4. Avalia os 404 do RSS da rodada inteira (instabilidade geral x canal removido)
        try:
            evaluate_rss_not_found(rss_404_suspects, len(channels))
        except Exception as e:
            logger.error(f"Erro ao avaliar canais com RSS 404: {e}")

        check_progress['status'] = 'Concluído'
    
    except Exception as e:
        logger.error(f"Erro fatal na verificação: {e}")
        check_progress['status'] = 'Erro'
    finally:
        check_progress['running'] = False
        last_check_time = datetime.now()
        
        # Verifica transição novamente ao finalizar
        # Isso garante que se o horário mudou DURANTE a execução (ex: 06:59 -> 07:01),
        # o aviso de "Bom dia" sai agora, antes de processar a fila.
        check_mute_transition()
        
        # Tenta processar a fila ao final de cada ciclo (se o horário permitir)
        process_notification_queue()
