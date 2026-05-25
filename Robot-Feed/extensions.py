"""
extensions.py - Inicialização de plugins Flask (DB, Scheduler)
Para evitar importação circular, separamos a inicialização aqui.
"""

from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler

# Inicializa sem aplicação (Factory Pattern)
db = SQLAlchemy()
scheduler = BackgroundScheduler()
