"""
Blueprints de Monitoramento de Canais
Rotas para gerenciar e monitorar canais do YouTube
"""

import os
import logging
import threading
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from extensions import db, scheduler
from models import Channel, get_config
from telegram_bot import send_telegram_message
from feed_service import check_progress, get_last_check_time
import feedparser
import requests

# Criar blueprint
monitor_bp = Blueprint('monitor', __name__)

logger = logging.getLogger(__name__)

# Referência global ao arquivo de log (será injetada por app.py)
# Veja setup_monitor_blueprint() abaixo
log_path = None
check_feeds_with_context = None


def setup_monitor_blueprint(app, log_path_ref, check_feeds_func):
    """
    Injeta dependências globais no blueprint.
    Deve ser chamado em app.py após criar o app e antes de registrar o blueprint.
    
    Args:
        app: Instância do Flask app
        log_path_ref: Caminho para o arquivo de log
        check_feeds_func: Função para verificar feeds
    """
    global log_path, check_feeds_with_context
    log_path = log_path_ref
    check_feeds_with_context = check_feeds_func


@monitor_bp.route('/')
def index():
    """Renderiza a página principal de monitoramento"""
    channels = Channel.query.all()
    # Ordena: Lives primeiro, depois por data de publicação (mais recente primeiro)
    channels.sort(key=lambda c: (c.is_live or False, c.last_video_published or ''), reverse=True)
    config = get_config()

    # Lógica de Tempo (Última e Próxima Verificação)
    job = scheduler.get_job('feed_job')
    next_check_str = "--"
    last_check_str = "--:--"

    last_check_time = get_last_check_time()
    if last_check_time:
        last_check_str = last_check_time.strftime('%H:%M')
    
    if job and job.next_run_time:
        try:
            now = datetime.now(job.next_run_time.tzinfo)
            delta = job.next_run_time - now
            minutes = int(delta.total_seconds() / 60)
            next_check_str = f"{max(0, minutes)} min"
        except Exception:
            pass

    return render_template('index.html', channels=channels, config=config, last_check=last_check_str, next_check=next_check_str, active_page='monitor')


@monitor_bp.route('/add_channel', methods=['POST'])
def add_channel():
    """Adiciona um novo canal à lista de monitoramento"""
    identifier = request.form.get('identifier', '').strip()
    conf = get_config()
    
    if identifier:
        # 1. Tenta obter detalhes via API externa
        api_url = conf.youtube_api_url or "http://host.docker.internal:8000"
        # Remove barra final se houver para evitar erro na URL
        if api_url.endswith('/'): api_url = api_url[:-1]
        
        try:
            response = requests.get(f"{api_url}/api/get-channel-details/{identifier}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                c_id = data.get('id')
                name = data.get('title')
            else:
                flash(f'Erro na API: Não foi possível encontrar o canal "{identifier}".', 'error')
                return redirect(url_for('monitor.index'))
        except Exception as e:
            flash(f'Erro ao conectar na API de Detalhes: {e}', 'error')
            return redirect(url_for('monitor.index'))

        # Verifica se já existe
        if Channel.query.filter_by(channel_id=c_id).first():
            flash(f'O canal "{name}" já está cadastrado.', 'error')
            return redirect(url_for('monitor.index'))

        # Busca o último vídeo atual para não notificar vídeos antigos na hora do cadastro
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={c_id}"
        last_vid = None
        try:
            feed = feedparser.parse(rss_url)
            if feed.entries:
                last_vid = getattr(feed.entries[0], 'yt_videoid', None)
        except Exception:
            pass # Se falhar, entra como None e notificará o próximo

        new_channel = Channel(name=name, channel_id=c_id, last_video_id=last_vid)
        db.session.add(new_channel)
        db.session.commit()
        logger.info(f"Novo canal adicionado: {name} ({c_id})")
        flash(f'Canal "{name}" adicionado com sucesso!', 'success')
    else:
        flash('Por favor, informe o identificador do canal.', 'error')
        
    return redirect(url_for('monitor.index'))


@monitor_bp.route('/update_config', methods=['POST'])
def update_config():
    """Atualiza as configurações globais do sistema"""
    try:
        from models import Config
        
        # Obtém a configuração atual
        conf = get_config()
        
        # Atualiza os campos
        if request.form.get('interval'):
            conf.check_interval_minutes = int(request.form.get('interval'))
        
        if request.form.get('cooldown'):
            conf.live_cooldown_minutes = int(request.form.get('cooldown'))
        
        # Modo silencioso (madrugada)
        mute_start = request.form.get('mute_start', '-1')
        mute_end = request.form.get('mute_end', '-1')
        
        conf.mute_start_hour = int(mute_start) if int(mute_start) >= 0 else None
        conf.mute_end_hour = int(mute_end) if int(mute_end) >= 0 else None
        
        # Telegram
        if request.form.get('tg_token'):
            conf.telegram_token = request.form.get('tg_token').strip()
        
        if request.form.get('tg_chat_id'):
            conf.telegram_chat_id = request.form.get('tg_chat_id').strip()
        
        # API URLs
        if request.form.get('api_url'):
            conf.youtube_api_url = request.form.get('api_url').strip()
        
        # Salva as mudanças
        db.session.commit()
        logger.info("✅ Configurações atualizadas com sucesso")
        
        # Atualiza o scheduler se o intervalo foi modificado
        if request.form.get('interval'):
            try:
                scheduler.reschedule_job(
                    'feed_job',
                    trigger='interval',
                    minutes=conf.check_interval_minutes
                )
                logger.info(f"⚙️ Scheduler atualizado: {conf.check_interval_minutes} minutos")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao atualizar scheduler: {e}")
        
        flash('✅ Configurações atualizadas com sucesso!', 'success')
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar configurações: {e}")
        db.session.rollback()
        flash(f'❌ Erro ao atualizar: {str(e)}', 'error')
    
    return redirect(url_for('monitor.index'))

@monitor_bp.route('/toggle_mute/<int:id>')
def toggle_mute(id):
    """Alterna o silêncio de notificações de um canal"""
    channel = Channel.query.get(id)
    if channel:
        # Lógica Inteligente:
        # 1. Se estiver AO VIVO, o botão alterna o silêncio APENAS daquela live específica.
        if channel.is_live and channel.last_live_id:
            if channel.muted_live_id == channel.last_live_id:
                channel.muted_live_id = None # Reativar avisos desta live
                flash(f'Avisos reativados para a live atual de "{channel.name}".', 'success')
            else:
                channel.muted_live_id = channel.last_live_id # Silenciar esta live
                flash(f'Live atual de "{channel.name}" foi silenciada. Próximas lives avisarão normalmente.', 'success')
        
        # 2. Se NÃO estiver ao vivo, o botão alterna o silêncio GLOBAL.
        else:
            channel.mute_notifications = not channel.mute_notifications
            status = "silenciado" if channel.mute_notifications else "ativado"
            flash(f'Notificações de "{channel.name}" foram {status} (Global).', 'success')
            
        db.session.commit()
        logger.info(f"Toggle mute para canal {id}: {channel.name}")
    return redirect(url_for('monitor.index'))


@monitor_bp.route('/delete_channel/<int:id>')
def delete_channel(id):
    """Deleta um canal da lista de monitoramento"""
    channel = Channel.query.get(id)
    if channel:
        channel_name = channel.name
        db.session.delete(channel)
        db.session.commit()
        logger.info(f"Canal deletado: {channel_name}")
        flash('Canal removido.', 'success')
    return redirect(url_for('monitor.index'))


@monitor_bp.route('/force_check')
def force_check():
    """Rota para forçar uma verificação manual imediata dos feeds"""
    if check_feeds_with_context is None:
        logger.error("check_feeds_with_context não foi configurado no blueprint")
        return jsonify({'status': 'error', 'message': 'Sistema não inicializado'}), 500
    
    if not check_progress['running']:
        # Inicia em uma thread separada para não travar o navegador
        thread = threading.Thread(target=check_feeds_with_context)
        thread.start()
        logger.info("Verificação manual iniciada")
        return jsonify({'status': 'started'})
    else:
        return jsonify({'status': 'already_running'})


@monitor_bp.route('/progress')
def get_progress():
    """Retorna o estado atual da verificação para o frontend"""
    return jsonify(check_progress)


@monitor_bp.route('/logs')
def view_logs():
    """Rota para visualizar os logs do sistema"""
    if log_path is None:
        logger.error("log_path não foi configurado no blueprint")
        return jsonify({'error': 'Sistema não inicializado'}), 500
    
    show_full = request.args.get('full') == 'true'
    
    # Garante que log_path é um arquivo, não um diretório
    if not os.path.isfile(log_path):
        logger.warning(f"Arquivo de log não encontrado em: {log_path}")
        return jsonify(["Arquivo de log não encontrado. Aguarde a primeira execução do sistema."])
    
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Se não pediu log completo, filtra os DEBUGs
        if not show_full:
            # Mantém apenas INFO, WARNING, ERROR e CRITICAL
            lines = [line for line in lines if 'DEBUG' not in line]
            
        # Retorna as últimas 100 linhas em formato JSON para o modal
        return jsonify(lines[-100:])
    except Exception as e:
        logger.error(f"Erro ao ler arquivo de logs: {e}")
        return jsonify({"error": f"Erro ao ler logs: {str(e)}"}), 500


@monitor_bp.route('/docs')
def docs_index():
    """Renderiza a interface da Documentação da API embutida (Iframe)"""
    conf = get_config()
    api_url = conf.youtube_api_url or "http://192.168.0.13:8000"
    if api_url.endswith('/'): 
        api_url = api_url[:-1]
    docs_url = f"{api_url}/docs"
    return render_template('docs.html', active_page='docs', docs_url=docs_url)


@monitor_bp.route('/test_notification')
def test_notification():
    """Rota para testar o envio de mensagem"""
    success, msg = send_telegram_message("🔔 Teste de notificação do Robot Feed!")
    if success:
        flash('✅ Sucesso! Mensagem enviada para o Telegram.', 'success')
    else:
        flash(f'❌ Falha no envio: {msg}', 'error')
    return redirect(url_for('monitor.index'))


@monitor_bp.route('/get_chat_id')
def get_chat_id():
    """Rota auxiliar para descobrir o ID do Chat/Grupo"""
    conf = get_config()
    if not conf.telegram_token:
        return jsonify({"erro": "Token não configurado"})
    
    url = f"https://api.telegram.org/bot{conf.telegram_token}/getUpdates"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        found_chats = []
        if data.get('ok'):
            for result in data.get('result', []):
                # Verifica mensagens normais e mensagens de "meu chat" (my_chat_member)
                msg = result.get('message') or result.get('my_chat_member') or result.get('channel_post')
                if msg and 'chat' in msg:
                    chat = msg['chat']
                    info = f"ID: {chat['id']} | Tipo: {chat['type']} | Nome: {chat.get('title', chat.get('username', 'Sem nome'))}"
                    if info not in found_chats:
                        found_chats.append(info)
                        logger.info(f"🕵️ CHAT DESCOBERTO: {info}")
        
        return jsonify(found_chats if found_chats else ["Nenhuma mensagem recente encontrada. Envie algo no grupo e tente novamente."])
    except Exception as e:
        return jsonify({"erro": str(e)})


@monitor_bp.route('/test_live/<int:id>')
def test_live(id):
    """Simula uma notificação de Live para um canal específico"""
    channel = Channel.query.get(id)
    if channel:
        # Cria uma mensagem simulada
        msg = (f"🔴 <b>TESTE DE LIVE: {channel.name}</b>\n\n"
               f"🔗 https://www.youtube.com/channel/{channel.channel_id}")
        
        success, ret_msg = send_telegram_message(msg)
        if success:
            flash(f'📢 Simulação de Live enviada para "{channel.name}"!', 'success')
        else:
            flash(f'❌ Erro ao enviar simulação: {ret_msg}', 'error')
    else:
        flash('Canal não encontrado.', 'error')
        
    return redirect(url_for('monitor.index'))


@monitor_bp.route('/export_channels')
def export_channels():
    """Exporta a lista de canais para JSON no formato compatível"""
    channels = Channel.query.all()
    # Formato: [{"id": "CHANNEL_ID", "title": "CHANNEL_NAME"}]
    data = [{"id": c.channel_id, "title": c.name} for c in channels]
    
    response = jsonify(data)
    response.headers["Content-Disposition"] = "attachment; filename=canais_backup.json"
    return response


@monitor_bp.route('/import_channels', methods=['POST'])
def import_channels():
    """Importa canais de um arquivo JSON"""
    import json
    
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('monitor.index'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('monitor.index'))

    if file:
        try:
            data = json.load(file)
            
            if not isinstance(data, list):
                flash('Formato inválido: O arquivo deve conter uma lista JSON.', 'error')
                return redirect(url_for('monitor.index'))
            
            count = 0
            for item in data:
                c_id = item.get('id')
                name = item.get('title')
                
                if c_id and name:
                    # Verifica se já existe para não duplicar
                    if not Channel.query.filter_by(channel_id=c_id).first():
                        # Tenta pegar o último vídeo para evitar notificação antiga imediata
                        last_vid = None
                        try:
                            rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={c_id}"
                            feed = feedparser.parse(rss_url)
                            if feed.entries:
                                last_vid = getattr(feed.entries[0], 'yt_videoid', None)
                        except Exception:
                            pass
                        
                        new_channel = Channel(name=name, channel_id=c_id, last_video_id=last_vid)
                        db.session.add(new_channel)
                        count += 1
            
            db.session.commit()
            if count > 0:
                flash(f'{count} canais importados com sucesso!', 'success')
            else:
                flash('Nenhum canal novo encontrado no arquivo.', 'info')
                
        except json.JSONDecodeError:
            flash('Erro: O arquivo não é um JSON válido.', 'error')
        except Exception as e:
            flash(f'Erro na importação: {str(e)}', 'error')
            
    return redirect(url_for('monitor.index'))
