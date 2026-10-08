"""
telegram_bot.py - Lógica de Telegram, fila de mensagens e modo silencioso
"""

import logging
import requests
import time
import threading
import re
from datetime import datetime, timedelta
from models import Config, NotificationQueue, get_config
from extensions import db

logger = logging.getLogger(__name__)

# Variável global para controlar estado do Mute
mute_status = {'active': False}


def is_mute_active(conf):
    """Verifica se estamos no horário de silêncio"""
    if conf.mute_start_hour == -1 or conf.mute_end_hour == -1:
        return False
    
    now_hour = datetime.now().hour
    start = conf.mute_start_hour
    end = conf.mute_end_hour

    # Ex: 23h até 07h (passa pela meia-noite)
    if start > end:
        return now_hour >= start or now_hour < end
    # Ex: 01h até 05h (mesmo dia)
    else:
        return start <= now_hour < end


def send_telegram_message(message, force=False):
    """Envia notificação para o Telegram ou enfileira se estiver em modo silencioso"""
    conf = get_config()
    if not conf.telegram_token or not conf.telegram_chat_id:
        logger.warning("Telegram não configurado. Mensagem ignorada.")
        return False, "Telegram não configurado."
    
    # Verifica Modo Silencioso
    if not force and is_mute_active(conf):
        # Verifica duplicidade na fila pendente
        exists = NotificationQueue.query.filter_by(message=message, status='pending').first()
        if not exists:
            new_item = NotificationQueue(message=message)
            db.session.add(new_item)
            db.session.commit()
            logger.info(f"Modo Silencioso ATIVO: Mensagem enfileirada (ID: {new_item.id}). Conteúdo: {message[:50]}...")
            return True, "Enfileirado (Modo Silencioso)"
        logger.info(f"Modo Silencioso: Mensagem duplicada ignorada. Conteúdo: {message[:50]}...")
        return True, "Duplicado na fila (Ignorado)"
    
    # Log detalhado para diagnóstico (mascarando o token para segurança)
    token_masked = f"{conf.telegram_token[:5]}...{conf.telegram_token[-5:]}" if conf.telegram_token and len(conf.telegram_token) > 10 else "***"
    logger.debug(f"Telegram: Tentando enviar mensagem... Chat ID: {conf.telegram_chat_id} | Token: {token_masked}")

    url = f"https://api.telegram.org/bot{conf.telegram_token}/sendMessage"
    payload = {
        "chat_id": conf.telegram_chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            # Log Limpo: Apenas confirmação
            logger.info("Telegram: Mensagem enviada com sucesso! ✅")
            # Log Técnico (DEBUG): O JSON completo com offsets, bolds, etc.
            logger.debug(f"Telegram API Raw: {response.text}")
            return True, "Sucesso"
        else:
            # Melhora o log para identificar erro comum de "chat not found"
            error_msg = response.text
            if response.status_code == 400 and "chat not found" in error_msg:
                error_msg += " -> DICA: Você iniciou a conversa com o bot? Envie /start para ele no Telegram."
            logger.error(f"Telegram: Erro na API (Status {response.status_code}): {error_msg}")
            return False, f"Erro API ({response.status_code}): {error_msg}"
    except Exception as e:
        logger.error(f"Telegram: Falha de Conexão (Exception): {e}")
        return False, f"Erro de Conexão: {str(e)}"


def process_notification_queue():
    """Processa a fila de mensagens pendentes se fora do horário de silêncio"""
    conf = get_config()
    
    # Se ainda estiver no horário mudo, não faz nada
    if is_mute_active(conf):
        return

    pending_msgs = NotificationQueue.query.filter_by(status='pending').order_by(NotificationQueue.created_at).all()
    
    if pending_msgs:
        logger.info(f"Processando fila de notificações: {len(pending_msgs)} mensagens.")
        sent_count = 0
        
        for item in pending_msgs:
            # Envia usando a lógica direta da API (bypassando a função send_telegram_message para evitar loop)
            url = f"https://api.telegram.org/bot{conf.telegram_token}/sendMessage"
            payload = {"chat_id": conf.telegram_chat_id, "text": item.message, "parse_mode": "HTML"}
            try:
                requests.post(url, json=payload, timeout=10)
                # Marca como enviado ou deleta
                db.session.delete(item)
                sent_count += 1
            except Exception as e:
                logger.error(f"Erro ao processar fila msg {item.id}: {e}")
                # Mantém na fila para tentar depois ou marca erro? Vamos manter por enquanto.
        
        db.session.commit()
        logger.info(f"Fila de notificações processada. {sent_count}/{len(pending_msgs)} enviadas.")


def check_mute_transition():
    """Verifica transição do Modo Silencioso e notifica"""
    global mute_status
    conf = get_config()
    
    # Se Mute desativado na config, reseta status e sai
    if conf.mute_start_hour == -1 or conf.mute_end_hour == -1:
        mute_status['active'] = False
        return

    is_active = is_mute_active(conf)
    
    # Transição: Entrando no Modo Silencioso (Normal -> Mute)
    if not mute_status['active'] and is_active:
        send_telegram_message("🌙 <b>Boa noite!</b>\nEntrando no Modo Silencioso. As notificações serão guardadas até o amanhecer.", force=True)
        mute_status['active'] = True
        logger.info("Mute: Transição para ATIVO detectada.")

    # Transição: Saindo do Modo Silencioso (Mute -> Normal)
    elif mute_status['active'] and not is_active:
        pending = NotificationQueue.query.filter_by(status='pending').count()
        if pending > 0:
            msg = f"☀️ <b>Bom dia!</b>\nO Modo Silencioso acabou. Preparando {pending} notificações retidas..."
        else:
            msg = "☀️ <b>Bom dia!</b>\nO Modo Silencioso acabou. Nenhuma notificação pendente."
        
        send_telegram_message(msg, force=True)
        mute_status['active'] = False
        logger.info("Mute: Transição para INATIVO detectada.")

last_update_id = 0

def process_telegram_command(message_text, app):
    """Processa comandos recebidos do Telegram"""
    if message_text.startswith('/resume '):
        video_url = message_text.split('/resume ')[1].strip()
        send_telegram_message(f"⏳ <b>Recebido!</b> Extraindo transcrição e gerando resumo para:\n{video_url}", force=True)
        
        def run_summary(app_instance):
            with app_instance.app_context():
                try:
                    # Aumentamos a paciência para 5 minutos (300s) pois a IA pode demorar
                    resp = requests.post('http://127.0.0.1:5000/api/resumo', json={'video_url': video_url}, timeout=300)
                    
                    if resp.status_code == 200:
                        # A SUA IDEIA AQUI: Buscar direto do Cofre!
                        from models import VideoArchive # Importação local segura
                        
                        # Tenta extrair o video_id da URL enviada
                        video_id = None
                        if 'v=' in video_url:
                            video_id = video_url.split('v=')[1].split('&')[0]
                        elif 'youtu.be/' in video_url:
                            video_id = video_url.split('youtu.be/')[1].split('?')[0]
                        elif '/shorts/' in video_url:
                            video_id = video_url.split('/shorts/')[1].split('?')[0]
                            
                        # Procura no banco de dados o registro que o app.py acabou de salvar
                        if video_id:
                            archive = VideoArchive.query.filter_by(video_id=video_id).first()
                            if archive:
                                # Pega os dados direto do banco!
                                summary_text = archive.summary
                                title = archive.title
                                
                                # Extrai a conclusão
                                # Extrai a conclusão de forma inteligente
                                import re
                                
                                # Quebra o texto usando qualquer linha que pareça um título de "Conclusão"
                                parts = re.split(r'(?im)^.*(?:#+\s*Conclusão|\*\*Conclusão\*\*|Conclusão:).*$', summary_text)
                                
                                if len(parts) > 1:
                                    # Pegamos a última parte garantindo ser a conclusão final
                                    conclusao = parts[-1].strip()
                                else:
                                    # Fallback
                                    conclusao = "... " + summary_text[-800:].strip()

                                # BÔNUS: Converte o **negrito** do Markdown para <b>negrito</b> do HTML do Telegram
                                conclusao = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', conclusao)
                                
                                if len(parts) > 1:
                                    msg_final = f"✅ <b>Resumo Salvo no Cofre!</b>\n📺 <i>{title}</i>\n\n<b>📌 Conclusão:</b>\n{conclusao}"
                                else:
                                    msg_final = f"✅ <b>Resumo Salvo no Cofre!</b>\n📺 <i>{title}</i>\n\n<b>📌 Trecho Final:</b>\n{conclusao}"
                                
                                send_telegram_message(msg_final, force=True)
                                return # Termina a função com sucesso
                        
                        # Fallback: Se não achou no banco, avisa que concluiu mas não achou o texto
                        send_telegram_message("✅ <b>Resumo finalizado!</b>\nEle já deve estar no seu Cofre, mas não consegui extrair o texto agora.", force=True)
                    else:
                        send_telegram_message(f"❌ <b>Erro ao resumir:</b> O servidor retornou status {resp.status_code}.", force=True)
                except Exception as e:
                    # Agora o erro não será mais silencioso! Ele vai para o log e para o seu Telegram.
                    logger.error(f"Erro na thread de resumo do Telegram: {e}")
                    send_telegram_message(f"❌ <b>Tempo esgotado ou Erro Interno:</b> {str(e)}\n\nO vídeo pode ter sido salvo no cofre em segundo plano.", force=True)
                
        threading.Thread(target=run_summary, args=(app,)).start()

    elif message_text.startswith('/fila '):
        video_url = message_text.split('/fila ')[1].strip()
        
        def add_to_queue(app_instance):
            with app_instance.app_context():
                try:
                    from models import SummaryQueue
                    novo_item = SummaryQueue(video_url=video_url)
                    db.session.add(novo_item)
                    db.session.commit()
                    
                    # Conta quantos estão na fila
                    posicao = SummaryQueue.query.filter_by(status='pending').count()
                    send_telegram_message(f"📥 <b>Adicionado à Fila!</b>\nO vídeo será processado gradativamente.\n📍 Posição na fila: {posicao}", force=True)
                except Exception as e:
                    send_telegram_message(f"❌ Erro ao adicionar à fila: {e}", force=True)
                    
        threading.Thread(target=add_to_queue, args=(app,)).start()

    elif message_text.strip().lower() in ['/help', '/ajuda']:
        help_msg = (
            "🤖 <b>Menu de Comandos do Robot Feed</b>\n\n"
            "Aqui estão os comandos que eu entendo até o momento:\n\n"
            "📝 <b>/resume [URL_DO_VIDEO]</b>\n"
            "↳ <i>Baixa, transcreve e gera o resumo de um vídeo imediatamente. Salva no cofre ao finalizar.</i>\n\n"
            "📥 <b>/fila [URL_DO_VIDEO]</b>\n"
            "↳ <i>Adiciona o vídeo à fila de processamento em segundo plano para não sobrecarregar a API.</i>\n\n"
            "🧹 <b>/limparplex</b>\n"
            "↳ <i>Remove todos os vídeos já assistidos do servidor Plex.</i>\n\n"
            "💡 <i>Dica: Envie o link completo do YouTube ou o link curto (youtu.be).</i>"
        )
        send_telegram_message(help_msg, force=True)

    elif message_text.strip().lower() in ['/limparplex', '/limpar_plex', '/limpar']:
        send_telegram_message("🧹 <b>Limpando Plex...</b>\nSolicitando a exclusão dos vídeos assistidos.", force=True)
        
        def run_plex_cleanup(app_instance):
            with app_instance.app_context():
                try:
                    # Faz a requisição DELETE para o seu backend (ajuste o IP se necessário)
                    url = 'http://192.168.0.11:8000/plex/limpar-assistidos'
                    resp = requests.delete(url, timeout=60)
                    
                    if resp.status_code == 200:
                        data = resp.json()
                        mensagem_principal = data.get('message', 'Limpeza concluída.')
                        apagados = data.get('apagados', [])
                        
                        if apagados:
                            # Formata a lista com um emoji de lixeira para cada item
                            lista_formatada = "\n".join([f"🗑️ <i>{video}</i>" for video in apagados])
                            msg_final = f"✅ <b>Limpeza Concluída!</b>\n{mensagem_principal}\n\n<b>Vídeos Removidos:</b>\n{lista_formatada}"
                        else:
                            msg_final = f"✅ <b>Limpeza Concluída!</b>\n{mensagem_principal}\nNenhum vídeo precisou ser removido."
                            
                        send_telegram_message(msg_final, force=True)
                    else:
                        send_telegram_message(f"❌ <b>Erro na limpeza do Plex:</b> O servidor retornou status {resp.status_code}.", force=True)
                except requests.Timeout:
                    send_telegram_message("❌ <b>Erro:</b> O servidor demorou muito para responder (Timeout).", force=True)
                except Exception as e:
                    logger.error(f"Erro na thread de limpeza do Plex: {e}")
                    send_telegram_message(f"❌ <b>Erro Interno de Conexão:</b> {str(e)}", force=True)
                
        threading.Thread(target=run_plex_cleanup, args=(app,)).start()

def telegram_polling_worker(app):
    """Loop infinito que busca novas mensagens no Telegram"""
    global last_update_id
    while True:
        try:
            with app.app_context():
                conf = get_config()
                if not conf.telegram_token:
                    time.sleep(10)
                    continue
                    
                url = f"https://api.telegram.org/bot{conf.telegram_token}/getUpdates?offset={last_update_id + 1}&timeout=10"
                response = requests.get(url, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    for result in data.get('result', []):
                        last_update_id = result['update_id']
                        # Alteração aqui: Lê DM/Grupos ('message') OU Canais ('channel_post')
                        msg = result.get('message') or result.get('channel_post')
                        
                        if msg and 'text' in msg:
                            process_telegram_command(msg['text'], app)
        except Exception as e:
            logger.error(f"Erro no polling do Telegram: {e}")
            
        time.sleep(2) # Pausa curta antes de perguntar de novo

def start_telegram_polling(app):
    """Inicia a thread do ouvinte do Telegram"""
    thread = threading.Thread(target=telegram_polling_worker, args=(app,), daemon=True)
    thread.start()
    logger.info("Ouvinte de comandos do Telegram iniciado.")
