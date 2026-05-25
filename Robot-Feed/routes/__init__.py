"""
Blueprints de Rotas - Organização modular das rotas da aplicação.

Módulos:
    - monitor_bp: Rotas de monitoramento de canais ✅
    - resumo_bp: Rotas de resumo de vídeos ✅
    - leiloes_bp: Rotas de sistema de leilões ✅
    - (futuro) config_bp: Rotas de configuração
    - (futuro) archive_bp: Rotas do Cofre de Conhecimento

Exemplo de uso em app.py:
    from routes import monitor_bp, setup_monitor_blueprint
    from routes import resumo_bp, setup_resumo_blueprint
    from routes import leiloes_bp, setup_leiloes_blueprint
    
    # Setup de injeção de dependências
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    setup_resumo_blueprint(app, log_path, processar_fila_resumos)
    setup_leiloes_blueprint(app, log_path)
    
    # Registrar blueprints
    app.register_blueprint(monitor_bp)
    app.register_blueprint(resumo_bp)
    app.register_blueprint(leiloes_bp)
"""

from routes.monitor import monitor_bp, setup_monitor_blueprint
from routes.resumo import resumo_bp, setup_resumo_blueprint
from routes.leiloes import leiloes_bp, setup_leiloes_blueprint

__all__ = [
    'monitor_bp',
    'setup_monitor_blueprint',
    'resumo_bp',
    'setup_resumo_blueprint',
    'leiloes_bp',
    'setup_leiloes_blueprint',
]
