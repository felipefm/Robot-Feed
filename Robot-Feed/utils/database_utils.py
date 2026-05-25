"""
Utilitários de banco de dados para Robot Feed.
Gerencia migrações, inspections e operações de dados.
"""

import logging
from sqlalchemy import text
from extensions import db


logger = logging.getLogger(__name__)


def inspect_and_migrate() -> None:
    """
    Verifica e atualiza o banco de dados se faltarem colunas novas.
    
    Realiza migrações de schema automaticamente, adicionando colunas
    que possam estar faltando em uma atualização de versão.
    
    Raises:
        None: Captura exceções internamente e loga os erros
    """
    try:
        with db.engine.connect() as conn:
            # Adiciona coluna last_live_notify na tabela channel se não existir
            try:
                conn.execute(text("ALTER TABLE channel ADD COLUMN last_live_notify DATETIME"))
                logger.info("Migração: Coluna 'last_live_notify' adicionada.")
            except Exception:
                pass  # Coluna provavelmente já existe

            # Adiciona coluna live_cooldown_minutes na tabela config se não existir
            try:
                conn.execute(text("ALTER TABLE config ADD COLUMN live_cooldown_minutes INTEGER DEFAULT 120"))
                logger.info("Migração: Coluna 'live_cooldown_minutes' adicionada.")
            except Exception:
                pass

            # Migração para Modo Silencioso
            try:
                conn.execute(text("ALTER TABLE config ADD COLUMN mute_start_hour INTEGER DEFAULT -1"))
                conn.execute(text("ALTER TABLE config ADD COLUMN mute_end_hour INTEGER DEFAULT -1"))
                logger.info("Migração: Colunas de Modo Silencioso adicionadas.")
            except Exception:
                pass

            # Migração para Configurações de Leilão
            try:
                conn.execute(text("ALTER TABLE config ADD COLUMN auction_api_url VARCHAR(200) DEFAULT 'http://192.168.0.11:8000'"))
                logger.info("Migração: Coluna 'auction_api_url' adicionada.")
            except Exception:
                pass
            
            try:
                conn.execute(text("ALTER TABLE config ADD COLUMN auction_interval_minutes INTEGER DEFAULT 360"))
                logger.info("Migração: Coluna 'auction_interval_minutes' adicionada.")
            except Exception:
                pass

            # Migração para novos campos de vídeo (Thumb, Published, Duration)
            new_cols = {
                'last_video_thumb': 'VARCHAR(200)',
                'last_video_published': 'VARCHAR(50)',
                'last_video_duration': 'VARCHAR(20)',
                'is_live': 'BOOLEAN',
                'last_live_id': 'VARCHAR(50)',
                'last_live_thumb': 'VARCHAR(200)',
                'last_live_start': 'VARCHAR(50)',
                'last_live_duration': 'VARCHAR(20)'
            }
            for col_name, col_type in new_cols.items():
                try:
                    conn.execute(text(f"ALTER TABLE channel ADD COLUMN {col_name} {col_type}"))
                    logger.info(f"Migração: Coluna '{col_name}' adicionada.")
                except Exception:
                    pass

            # Migração para Mute por Canal
            try:
                conn.execute(text("ALTER TABLE channel ADD COLUMN mute_notifications BOOLEAN DEFAULT 0"))
                logger.info("Migração: Coluna 'mute_notifications' adicionada.")
            except Exception:
                pass

            # Migração para Mute Específico de Live
            try:
                conn.execute(text("ALTER TABLE channel ADD COLUMN muted_live_id VARCHAR(50)"))
                logger.info("Migração: Coluna 'muted_live_id' adicionada.")
            except Exception:
                pass

            # Migração para Agendamento de Leilão
            try:
                conn.execute(text("ALTER TABLE config ADD COLUMN auction_schedule_days VARCHAR(50) DEFAULT '0,1,2,3,4'"))
                logger.info("Migração: Coluna 'auction_schedule_days' adicionada.")
            except Exception:
                pass
            
            try:
                conn.execute(text("ALTER TABLE config ADD COLUMN auction_schedule_time VARCHAR(10) DEFAULT '05:00'"))
                logger.info("Migração: Coluna 'auction_schedule_time' adicionada.")
            except Exception:
                pass

            # Migração para novos campos no VideoArchive
            try:
                conn.execute(text("ALTER TABLE video_archive ADD COLUMN provider TEXT"))
                logger.info("Migração: Coluna 'provider' adicionada a video_archive.")
            except Exception:
                pass

            try:
                conn.execute(text("ALTER TABLE video_archive ADD COLUMN tokens_used INTEGER"))
                logger.info("Migração: Coluna 'tokens_used' adicionada a video_archive.")
            except Exception:
                pass

            # Bloco seguro para garantir a criação da tabela VideoArchive
            try:
                from models import VideoArchive
                VideoArchive.__table__.create(conn, checkfirst=True)
                logger.info("Migração: Tabela 'video_archive' verificada/criada com sucesso.")
            except Exception as e:
                logger.error(f"Erro ao verificar/criar tabela 'video_archive': {e}")

            # Tabela de Fila de Resumos
            try:
                from models import SummaryQueue
                SummaryQueue.__table__.create(conn, checkfirst=True)
                logger.info("Migração: Tabela 'summary_queue' verificada/criada.")
            except Exception as e:
                logger.error(f"Erro ao verificar/criar tabela 'summary_queue': {e}")
    
    except Exception as e:
        logger.error(f"Erro na migração de DB: {e}")
