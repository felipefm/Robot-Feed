"""
Robot Feed - App Principal (Minimalista)
Inicializa o Flask, configura o banco de dados, scheduler e registra todos os blueprints.
"""

import os
from datetime import datetime, timedelta
from flask import Flask, send_from_directory

# Imports das extensões e modelos
from extensions import db, scheduler
from models import Config, get_config, SummaryQueue, VideoArchive
from telegram_bot import send_telegram_message, start_telegram_polling
from feed_service import check_feeds
from utils import setup_logging, inspect_and_migrate
from utils.helpers import build_api_endpoint

# Imports dos blueprints
from routes import (
    monitor_bp, setup_monitor_blueprint,
    resumo_bp, setup_resumo_blueprint,
    leiloes_bp, setup_leiloes_blueprint
)

# ============================================================================
# CONFIGURAÇÃO DE CAMINHOS E LOGGING
# ============================================================================

base_dir = os.path.abspath(os.path.dirname(__file__))
data_dir = os.path.join(base_dir, 'data')
log_path = os.path.join(data_dir, 'robot.log')  # Arquivo real de log criado por setup_logging

logger = setup_logging(base_dir)

# ============================================================================
# INICIALIZAÇÃO DO FLASK
# ============================================================================

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configuração do Banco de Dados (SQLite)
db_path = os.path.join(data_dir, 'monitor.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar extensões
db.init_app(app)

# ============================================================================
# VARIÁVEIS GLOBAIS PARA BACKOFF INTELIGENTE
# ============================================================================

api_cooldown_until = None
current_backoff_minutes = 5

# ============================================================================
# JOBS DO SCHEDULER
# ============================================================================

def check_feeds_with_context():
    """Wrapper para check_feeds que fornece o app context"""
    with app.app_context():
        check_feeds()


def processar_fila_resumos():
    """
    Processa 1 vídeo pendente da fila de resumos com suporte a backoff inteligente.
    Reduz carga na API ao detectar quotas esgotadas.
    """
    global api_cooldown_until, current_backoff_minutes
    
    with app.app_context():
        import requests
        import re
        
        # Verifica se estamos em período de backoff (castigo por cota esgotada)
        if api_cooldown_until and datetime.now() < api_cooldown_until:
            logger.info(f"⏸️ Fila em Backoff: Pausa até {api_cooldown_until.strftime('%H:%M:%S')}")
            return
        
        # Pega o primeiro item pendente da fila
        item = SummaryQueue.query.filter_by(status='pending').order_by(SummaryQueue.created_at).first()
        if not item:
            return  # Fila vazia
        
        logger.info(f"🎬 Processando vídeo: {item.video_url}")
        
        try:
            # Envia para a API de resumo
            resp = requests.post(
                build_api_endpoint('/summarize-video', 'youtube'),
                json={'video_url': item.video_url},
                timeout=300
            )
            
            if resp.status_code == 200:
                # ✅ SUCESSO - Reseta o backoff
                current_backoff_minutes = 5
                api_cooldown_until = None
                
                result = resp.json()
                
                # Tenta arquivar o resultado
                try:
                    summary_text = result.get('summary', result.get('resumo', result.get('texto', '')))
                    if result.get('status') == 'success' or bool(summary_text):
                        # Extrai dados do vídeo
                        video_id = result.get('video_id')
                        title = result.get('title', 'Sem título')
                        
                        # Fallback se a IA não retornar o ID
                        if not video_id:
                            if 'v=' in item.video_url: video_id = item.video_url.split('v=')[1].split('&')[0]
                            elif 'youtu.be/' in item.video_url: video_id = item.video_url.split('youtu.be/')[1].split('?')[0]
                            elif '/shorts/' in item.video_url: video_id = item.video_url.split('/shorts/')[1].split('?')[0]
                        
                        # Verifica se já existe para não duplicar
                        existing = VideoArchive.query.filter_by(video_id=video_id).first() if video_id else None
                        if not existing and video_id and summary_text:
                            # Detecta qual canal o vídeo pertence
                            channel_id = result.get('channel_id', '')
                            channel_name = result.get('channel_name', 'Desconhecido')
                            published_at = result.get('published_at') or result.get('publication_date') or datetime.now().strftime('%Y-%m-%d')
                            
                            archive = VideoArchive(
                                channel_id=channel_id,
                                channel_name=channel_name,
                                video_id=video_id,
                                title=title,
                                published_at=published_at,
                                summary=summary_text,
                                full_transcript=result.get('transcript'),
                                extracted_tags=result.get('tags'),
                                provider=result.get('provider'),
                                tokens_used=result.get('tokens_used')
                            )
                            db.session.add(archive)
                            db.session.commit()
                            logger.info(f"✅ Vídeo arquivado no Cofre (Fila): {title}")
                        elif existing:
                            archive = existing
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao arquivar resultado da fila: {e}")
                
                item.status = 'completed'
                db.session.commit()
                
                # Extrai a conclusão do resumo e notifica via Telegram
                video_id = None
                if 'v=' in item.video_url:
                    video_id = item.video_url.split('v=')[1].split('&')[0]
                elif 'youtu.be/' in item.video_url:
                    video_id = item.video_url.split('youtu.be/')[1].split('?')[0]
                elif '/shorts/' in item.video_url:
                    video_id = item.video_url.split('/shorts/')[1].split('?')[0]
                
                if video_id:
                    archive = VideoArchive.query.filter_by(video_id=video_id).first()
                    if archive:
                        # Tenta extrair a seção de conclusão
                        parts = re.split(
                            r'(?im)^.*(?:#+\s*Conclusão|\*\*Conclusão\*\*|Conclusão:).*$',
                            archive.summary
                        )
                        conclusao = parts[-1].strip() if len(parts) > 1 else "... " + archive.summary[-800:].strip()
                        conclusao = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', conclusao)
                        
                        msg = (
                            f"✅ <b>Fila: Resumo Concluído!</b>\n"
                            f"📺 <i>{archive.title}</i>\n\n"
                            f"<b>📌 Conclusão:</b>\n{conclusao}"
                        )
                        send_telegram_message(msg, force=True)
            
            elif resp.status_code == 429 or "RESOURCE_EXHAUSTED" in resp.text:
                # ⚠️ COTA ESGOTADA - Ativa backoff inteligente
                api_cooldown_until = datetime.now() + timedelta(minutes=current_backoff_minutes)
                logger.warning(
                    f"⚠️ Cota da API atingida (429). Backoff: {current_backoff_minutes} minutos"
                )
                current_backoff_minutes = min(current_backoff_minutes * 3, 240)
            
            else:
                # ❌ ERRO - Marca como falha
                item.status = 'failed'
                db.session.commit()
                logger.error(f"❌ Erro {resp.status_code} ao resumir: {item.video_url}")
        
        except Exception as e:
            logger.error(f"❌ Erro na rotina de fila de resumos: {e}")


def update_scheduler():
    """Atualiza o intervalo do scheduler baseado na configuração"""
    conf = get_config()
    try:
        scheduler.reschedule_job(
            'feed_job',
            trigger='interval',
            minutes=conf.check_interval_minutes
        )
        logger.info(f"✅ Scheduler atualizado: {conf.check_interval_minutes} minutos")
    except Exception as e:
        logger.error(f"❌ Erro ao reagendar job: {e}")


# Adiciona os jobs ao scheduler
scheduler.add_job(func=check_feeds_with_context, trigger="interval", minutes=30, id='feed_job')
scheduler.add_job(func=processar_fila_resumos, trigger="interval", minutes=5, id='fila_resumos_job')
scheduler.start()

# ============================================================================
# ROTAS DE ARQUIVOS ESTÁTICOS
# ============================================================================

@app.route('/script.js')
def script():
    """Serve o arquivo script.js"""
    return send_from_directory(base_dir, 'script.js', mimetype='application/javascript')


@app.route('/style.css')
def style():
    """Serve o arquivo style.css"""
    return send_from_directory(base_dir, 'style.css', mimetype='text/css')


# ============================================================================
# SETUP DOS BLUEPRINTS
# ============================================================================

def setup_blueprints():
    """Registra todos os blueprints da aplicação"""
    logger.info("📦 Iniciando setup dos blueprints...")
    
    # Monitor Blueprint
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    app.register_blueprint(monitor_bp)
    logger.info("✅ Blueprint 'monitor_bp' registrado")
    
    # Resumo Blueprint
    setup_resumo_blueprint(app, log_path, processar_fila_resumos)
    app.register_blueprint(resumo_bp)
    logger.info("✅ Blueprint 'resumo_bp' registrado")
    
    # Leilões Blueprint
    setup_leiloes_blueprint(app, log_path)
    app.register_blueprint(leiloes_bp)
    logger.info("✅ Blueprint 'leiloes_bp' registrado")


# ============================================================================
# BLOCO PRINCIPAL
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        # Inspeciona e aplica migrações necessárias
        logger.info("🔍 Verificando integridade do banco de dados...")
        inspect_and_migrate()
        
        # Atualiza o intervalo do scheduler conforme configurado
        logger.info("⚙️ Configurando scheduler...")
        update_scheduler()
        
        # Envia mensagem de inicialização
        try:
            conf = get_config()
            if conf.telegram_token and conf.telegram_chat_id:
                send_telegram_message("🤖 Robot Feed: Sistema iniciado e monitorando!")
                logger.info("📢 Mensagem de inicialização enviada")
            else:
                logger.warning("⚠️ Telegram não configurado - aviso não enviado")
        except Exception as e:
            logger.error(f"❌ Erro ao enviar mensagem de inicialização: {e}")
        
        # Setup dos blueprints
        setup_blueprints()
        
        # Inicia o polling do Telegram
        logger.info("🔵 Iniciando listener de comandos do Telegram...")
        start_telegram_polling(app)
    
    # Inicia o servidor Flask
    logger.info("🚀 Iniciando servidor Flask na porta 5000...")
    app.run(host='0.0.0.0', port=5000)
