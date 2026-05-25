"""
EXEMPLOS PRÁTICOS: Como usar a nova estrutura modularizada

Demonstra casos reais de uso dos novos módulos utils/
"""

# ============================================================================
# EXEMPLO 1: Usando logging em um novo módulo (ex: feed_service.py)
# ============================================================================

# Antes (sem setup_logging):
# import logging
# logger = logging.getLogger(__name__)
# # Sem formatação consistente, sem filtros aplicados

# Depois (com setup_logging já rodando em app.py):
import logging

logger = logging.getLogger(__name__)

def check_feeds():
    """Verifica feeds de canais"""
    logger.info("Iniciando verificação de feeds...")
    try:
        # Sua lógica aqui
        logger.debug("Feeds verificados com sucesso")
    except Exception as e:
        logger.error(f"Erro ao verificar feeds: {e}", exc_info=True)
        

# ============================================================================
# EXEMPLO 2: Acessar logging em um módulo externo (ex: telegram_bot.py)
# ============================================================================

import logging

logger = logging.getLogger(__name__)

def send_telegram_message(message):
    """Envia mensagem ao Telegram"""
    logger.info(f"Enviando mensagem: {message[:50]}...")
    # A configuração de logging já está ativa globalmente
    # Por isso o message é formatado com data/hora automaticamente


# ============================================================================
# EXEMPLO 3: Teste de logging com filtro NoPollingLogFilter
# ============================================================================

import logging

# Este será silenciado pelo filtro NoPollingLogFilter:
logger = logging.getLogger('werkzeug')
logger.info("GET /progress")  # ❌ NÃO APARECERÁ nos logs

# Este será capturado normalmente:
logger.info("GET /api/status")  # ✅ APARECERÁ nos logs


# ============================================================================
# EXEMPLO 4: Usar inspect_and_migrate em um script externo
# ============================================================================

from flask import Flask
from extensions import db
from utils import inspect_and_migrate
import os

def initialize_database():
    """Script para inicializar banco de dados em qualquer lugar"""
    
    app = Flask(__name__)
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    # Configurar DB
    data_dir = os.path.join(base_dir, 'data')
    db_path = os.path.join(data_dir, 'monitor.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    db.init_app(app)
    
    # Usar a função centralizada
    with app.app_context():
        db.create_all()
        inspect_and_migrate()  # ✅ Reutilização em outro módulo!
        print("✅ Banco de dados inicializado e migrado")


# ============================================================================
# EXEMPLO 5: Estrutura futura com Blueprints (próxima fase)
# ============================================================================

# arquivo: routes/monitor.py
from flask import Blueprint, render_template
import logging

monitor_bp = Blueprint('monitor', __name__)
logger = logging.getLogger(__name__)

@monitor_bp.route('/')
def index():
    """Rota principal"""
    logger.info("Acessando página inicial")
    return render_template('index.html')

@monitor_bp.route('/add_channel', methods=['POST'])
def add_channel():
    """Adiciona novo canal"""
    logger.info("Novo canal sendo adicionado")
    # ...
    return redirect(...)


# arquivo: routes/config.py
from flask import Blueprint
import logging

config_bp = Blueprint('config', __name__)
logger = logging.getLogger(__name__)

@config_bp.route('/update_config', methods=['POST'])
def update_config():
    """Atualiza configurações"""
    logger.info("Configurações sendo atualizadas")
    # ...
    return redirect(...)


# arquivo: app.py (com blueprints)
from flask import Flask
from routes import monitor_bp, config_bp
from utils import setup_logging, inspect_and_migrate

app = Flask(__name__)

# Setup logging
base_dir = os.path.abspath(os.path.dirname(__file__))
logger = setup_logging(base_dir)

# Registrar blueprints
app.register_blueprint(monitor_bp)
app.register_blueprint(config_bp)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        inspect_and_migrate()
    app.run(host='0.0.0.0', port=5000)


# ============================================================================
# EXEMPLO 6: Importar múltiplos utilitários de uma vez
# ============================================================================

# Opção 1: Importar tudo
from utils import *

# Opção 2: Importar específicos
from utils import setup_logging, NoPollingLogFilter, inspect_and_migrate

# Opção 3: Importar cada módulo
from utils.logging_config import setup_logging, NoPollingLogFilter
from utils.database_utils import inspect_and_migrate


# ============================================================================
# EXEMPLO 7: Criar novo utilitário em utils/
# ============================================================================

# arquivo: utils/validators.py
"""Validadores customizados"""

def validate_channel_id(channel_id: str) -> bool:
    """Valida formato de ID de canal YouTube"""
    return len(channel_id) > 0 and channel_id.startswith('UC')

def validate_url(url: str) -> bool:
    """Valida URL do YouTube"""
    return 'youtube.com' in url or 'youtu.be' in url


# arquivo: utils/__init__.py (atualizado)
from utils.logging_config import setup_logging, NoPollingLogFilter
from utils.database_utils import inspect_and_migrate
from utils.validators import validate_channel_id, validate_url  # ✅ NOVO

__all__ = [
    'setup_logging',
    'NoPollingLogFilter',
    'inspect_and_migrate',
    'validate_channel_id',  # ✅ NOVO
    'validate_url',  # ✅ NOVO
]


# ============================================================================
# EXEMPLO 8: Usar validators em app.py
# ============================================================================

from flask import Flask, request, jsonify
from utils import validate_channel_id, validate_url
import logging

app = Flask(__name__)
logger = logging.getLogger(__name__)

@app.route('/add_channel', methods=['POST'])
def add_channel():
    identifier = request.form.get('identifier', '').strip()
    
    # Validar formato
    if not validate_channel_id(identifier):
        logger.warning(f"Tentativa de adicionar canal com ID inválido: {identifier}")
        return jsonify({'error': 'ID de canal inválido'}), 400
    
    # ... resto da lógica
    logger.info(f"Canal validado: {identifier}")
    return jsonify({'success': True})


# ============================================================================
# EXEMPLO 9: Logging em diferentes níveis
# ============================================================================

import logging

logger = logging.getLogger(__name__)

def example_logging_levels():
    """Demonstra os diferentes níveis de logging"""
    
    # DEBUG: Informações detalhadas para diagnóstico
    logger.debug("Iniciando processamento de 500 canais")
    
    # INFO: Informações gerais sobre o progresso
    logger.info("✅ Canais carregados com sucesso")
    
    # WARNING: Algo inesperado, mas não crítico
    logger.warning("API respondeu lentamente (5 segundos)")
    
    # ERROR: Erro que afeta funcionalidade
    logger.error("Falha ao conectar ao banco de dados", exc_info=True)
    
    # CRITICAL: Erro que afeta todo o sistema
    logger.critical("Espaço em disco cheio! Sistema pode parar.")


# ============================================================================
# EXEMPLO 10: Teste unitário com mocks
# ============================================================================

# arquivo: tests/test_database_utils.py
import unittest
from unittest.mock import patch, MagicMock
from utils import inspect_and_migrate

class TestDatabaseUtils(unittest.TestCase):
    
    @patch('utils.database_utils.db')
    def test_inspect_and_migrate_success(self, mock_db):
        """Testa migração bem-sucedida"""
        mock_conn = MagicMock()
        mock_db.engine.connect.return_value.__enter__.return_value = mock_conn
        
        # Executa a função
        inspect_and_migrate()
        
        # Verifica que execute foi chamado
        assert mock_conn.execute.called
        print("✅ Teste de migração passou")
    
    @patch('utils.database_utils.logger')
    @patch('utils.database_utils.db')
    def test_inspect_and_migrate_handles_error(self, mock_db, mock_logger):
        """Testa tratamento de erro"""
        mock_db.engine.connect.side_effect = Exception("DB Error")
        
        # Executa a função
        inspect_and_migrate()
        
        # Verifica que erro foi logado
        mock_logger.error.assert_called()
        print("✅ Teste de tratamento de erro passou")


if __name__ == '__main__':
    unittest.main()
