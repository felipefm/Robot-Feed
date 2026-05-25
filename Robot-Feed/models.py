"""
models.py - Modelos de Banco de Dados e funções relacionadas
"""

from datetime import datetime
from extensions import db

# --- MODELOS DO BANCO DE DADOS ---

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    channel_id = db.Column(db.String(50), nullable=False, unique=True)
    last_video_id = db.Column(db.String(50), nullable=True)
    last_live_notify = db.Column(db.DateTime, nullable=True)  # Data do último aviso de Live
    last_video_thumb = db.Column(db.String(200), nullable=True)
    last_video_published = db.Column(db.String(50), nullable=True)
    last_video_duration = db.Column(db.String(20), nullable=True)
    is_live = db.Column(db.Boolean, default=False)
    last_live_id = db.Column(db.String(50), nullable=True)
    last_live_thumb = db.Column(db.String(200), nullable=True)
    last_live_start = db.Column(db.String(50), nullable=True)
    last_live_duration = db.Column(db.String(20), nullable=True)
    mute_notifications = db.Column(db.Boolean, default=False)
    muted_live_id = db.Column(db.String(50), nullable=True)  # ID da live específica silenciada


class NotificationQueue(db.Model):
    """Fila de mensagens para envio posterior (Modo Noturno)"""
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default='pending')


class SummaryQueue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    video_url = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), default='pending') # pending, paused, completed, failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Config(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    check_interval_minutes = db.Column(db.Integer, default=30)
    live_cooldown_minutes = db.Column(db.Integer, default=120)  # Tempo de espera para repetir aviso de Live
    telegram_token = db.Column(db.String(100), nullable=True)
    telegram_chat_id = db.Column(db.String(50), nullable=True)
    youtube_api_url = db.Column(db.String(200), default='http://host.docker.internal:8000')
    mute_start_hour = db.Column(db.Integer, default=-1)  # -1 desativado
    mute_end_hour = db.Column(db.Integer, default=-1)
    auction_api_url = db.Column(db.String(200), default='http://192.168.0.6:8000')
    auction_interval_minutes = db.Column(db.Integer, default=360)  # Padrão 6 horas
    auction_schedule_days = db.Column(db.String(50), default='0,1,2,3,4')  # Dias da semana (0=Seg)
    auction_schedule_time = db.Column(db.String(10), default='05:00')  # Horário


# --- FUNÇÕES AUXILIARES ---

def get_config():
    """Recupera ou cria a configuração inicial"""
    conf = Config.query.first()
    if not conf:
        conf = Config(check_interval_minutes=30, live_cooldown_minutes=120)
        db.session.add(conf)
        db.session.commit()
    return conf


class VideoArchive(db.Model):
    __tablename__ = 'video_archive'
    
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.String(50), nullable=False)
    channel_name = db.Column(db.String(100), nullable=False) 
    video_id = db.Column(db.String(50), nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False)
    published_at = db.Column(db.String(50), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    full_transcript = db.Column(db.Text, nullable=True)
    extracted_tags = db.Column(db.String(255), nullable=True)
    archived_at = db.Column(db.DateTime, default=datetime.now)
    is_favorite = db.Column(db.Boolean, default=False)
    provider = db.Column(db.Text, nullable=True)
    tokens_used = db.Column(db.Integer, nullable=True)
