"""
Configuração centralizada de Logging para Robot Feed.
Gerencia logger, handlers e filtros de forma limpa e reutilizável.
"""

import os
import logging


def setup_logging(base_dir: str) -> logging.Logger:
    """
    Configura o sistema de logging da aplicação.
    
    Args:
        base_dir: Caminho base para armazenar arquivos de log
        
    Returns:
        logging.Logger: Logger configurado e pronto para uso
    """
    
    # Garante que a pasta data existe antes de criar logs
    data_dir = os.path.join(base_dir, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    log_path = os.path.join(data_dir, 'robot.log')
    
    # Configuração básica de logging
    logging.basicConfig(
        level=logging.DEBUG,  # Captura tudo, filtramos na visualização
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_path),
            logging.StreamHandler()
        ]
    )
    
    # Silencia logs excessivos de bibliotecas externas
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    
    logger = logging.getLogger(__name__)
    
    # Aplica filtro personalizado ao logger do Werkzeug
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.addFilter(NoPollingLogFilter())
    
    return logger


class NoPollingLogFilter(logging.Filter):
    """
    Filtro customizado para silenciar logs repetitivos de acesso.
    Remove mensagens contendo 'GET /progress' dos logs do servidor web.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filtra registros de log.
        
        Args:
            record: Registro de log a ser filtrado
            
        Returns:
            bool: True se o registro deve ser incluído, False caso contrário
        """
        return 'GET /progress' not in record.getMessage()
