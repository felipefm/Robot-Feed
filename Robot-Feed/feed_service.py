"""
feed_service.py - Serviço de verificação de feeds do YouTube
Núcleo da lógica de monitoramento de canais
"""

import logging
import requests
import feedparser
from datetime import datetime, timedelta
from models import Channel, get_config
from telegram_bot import send_telegram_message, check_mute_transition, process_notification_queue
from extensions import db

logger = logging.getLogger(__name__)

# Variável global para controlar o progresso da verificação
check_progress = {'current': 0, 'total': 0, 'status': 'idle', 'running': False}
last_check_time = None


def get_last_check_time():
    """Retorna a última vez que a verificação foi realizada"""
    return last_check_time


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
                        
                        # Coleta metadados do vídeo/live (Duração, Data, Thumb)
                        # Fazemos isso antes da notificação para salvar no banco de qualquer jeito
                        duration_str = None
                        try:
                            video_link = f"https://www.youtube.com/watch?v={video_id}"
                            dur_response = requests.get(f"{api_url}/api/get-live-duration", params={'video_url': video_link}, timeout=5)
                            if dur_response.status_code == 200:
                                dur_data = dur_response.json()
                                duration_str = dur_data.get('duration_str')
                                channel.last_live_duration = duration_str
                                channel.last_live_start = dur_data.get('start_time')
                        except Exception:
                            pass
                        
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
                            duration_info = ""
                            if duration_str:
                                duration_info = f"\n⏳ <b>No ar há:</b> {duration_str}"

                            msg = (f"🔴 <b>ESTÁ AO VIVO: {channel.name}</b>"
                                   f"{duration_info}\n\n"
                                   f"🔗 https://www.youtube.com/watch?v={video_id}")
                            
                            # Verifica se há Mute Global OU se esta Live específica foi silenciada
                            is_live_muted = (channel.muted_live_id == video_id)
                            if not channel.mute_notifications and not is_live_muted:
                                send_telegram_message(msg)
                            else:
                                logger.info(f"Notificação de LIVE silenciada ({'Global' if channel.mute_notifications else 'Específica'}) para: {channel.name}")
                            
                            channel.last_live_id = video_id
                            channel.last_live_notify = datetime.now() # Atualiza o relógio do cooldown
                        
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
                
                if feed.entries:
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
                            video_link = getattr(entry, 'link', f'https://www.youtube.com/watch?v={video_id}')
                            video_published = getattr(entry, 'published', None)
                            
                            # Evita notificar o vídeo se ele for a própria Live que já está rolando (ou acabou de acabar)
                            if video_id == channel.last_live_id:
                                channel.last_video_id = video_id
                                db.session.commit()
                                continue
                            
                            # Coleta metadados extras (Duração)
                            duration_str = None
                            try:
                                dur_response = requests.get(f"{api_url}/api/get-live-duration", params={'video_url': video_link}, timeout=5)
                                if dur_response.status_code == 200:
                                    dur_data = dur_response.json()
                                    duration_str = dur_data.get('duration_str')
                            except Exception:
                                pass
                            
                            video_thumb = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"

                            logger.info(f"NOVO VÍDEO DETECTADO: {channel.name} - {video_title}")
                            
                            duration_info = f"\n⏳ <b>Duração:</b> {duration_str}" if duration_str else ""
                            
                            msg = (f"🚨 <b>Novidade no Canal: {channel.name}</b>\n\n"
                                   f"📺 {video_title}"
                                   f"{duration_info}\n"
                                   f"🔗 {video_link}")
                            
                            if not channel.mute_notifications:
                                send_telegram_message(msg)
                            else:
                                logger.info(f"Notificação de VÍDEO silenciada para: {channel.name}")
                            
                            # Atualiza o banco passo a passo (garante que se falhar no meio, o que foi enviado fica salvo)
                            channel.last_video_id = video_id
                            channel.last_video_thumb = video_thumb
                            channel.last_video_published = video_published
                            channel.last_video_duration = duration_str
                            db.session.commit()
                    
                    # Se não tem vídeos novos, mas queremos atualizar metadados do último (caso falte)
                    elif not new_videos and feed.entries:
                        latest_entry = feed.entries[0]
                        video_id = getattr(latest_entry, 'yt_videoid', None)
                        
                        if video_id == channel.last_video_id:
                            missing_data = (not channel.last_video_thumb or 
                                          not channel.last_video_published or 
                                          not channel.last_video_duration)
                            
                            if missing_data:
                                # Recoleta dados para atualização visual
                                video_link = getattr(latest_entry, 'link', f'https://www.youtube.com/watch?v={video_id}')
                                video_published = getattr(latest_entry, 'published', None)
                                video_thumb = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                                
                                duration_str = None
                                try:
                                    dur_response = requests.get(f"{api_url}/api/get-live-duration", params={'video_url': video_link}, timeout=5)
                                    if dur_response.status_code == 200:
                                        dur_data = dur_response.json()
                                        duration_str = dur_data.get('duration_str')
                                except Exception:
                                    pass

                                channel.last_video_thumb = video_thumb
                                channel.last_video_published = video_published
                                if duration_str:
                                    channel.last_video_duration = duration_str
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
