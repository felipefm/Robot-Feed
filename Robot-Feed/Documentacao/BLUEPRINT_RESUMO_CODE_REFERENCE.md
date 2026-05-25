# 💻 BLUEPRINT RESUMO: Código de Referência Exato

Copie e cole o código exato de cada arquivo.

---

## 📄 ARQUIVO 1: `utils/helpers.py`

```python
"""
utils/helpers.py - Funções auxiliares reutilizáveis
"""

from models import get_config


def get_api_url(api_type='youtube'):
    """
    Formata e retorna a URL base da API remota, removendo barras finais.
    
    Args:
        api_type (str): Tipo de API - 'youtube' para resumo ou 'auction' para leilões
    
    Returns:
        str: URL formatada da API (sem barra final)
    """
    conf = get_config()
    
    if api_type == 'auction':
        url = conf.auction_api_url or 'http://192.168.0.6:8000'
    else:  # youtube (resumo)
        url = conf.youtube_api_url or "http://host.docker.internal:8000"
    
    # Remove barra final se existir
    return url.rstrip('/')


def format_url(url, **kwargs):
    """
    Formata uma URL com parâmetros nomeados.
    """
    return url.format(**kwargs)


def build_api_endpoint(path, api_type='youtube'):
    """
    Constrói uma URL completa de endpoint da API.
    """
    base_url = get_api_url(api_type)
    
    # Remove barra inicial do path se existir para evitar duplas
    if path.startswith('/'):
        path = path[1:]
    
    return f"{base_url}/{path}"
```

---

## 📄 ARQUIVO 2: `routes/resumo.py` - Primeiros 100 linhas

```python
"""
routes/resumo.py - Blueprint para gerenciamento de resumos de vídeo
"""

import logging
import requests
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from extensions import db
from models import VideoArchive, SummaryQueue
from utils.helpers import build_api_endpoint

logger = logging.getLogger(__name__)

resumo_bp = Blueprint('resumo', __name__)

log_path = None
processar_fila_resumos = None


def setup_resumo_blueprint(app, log_path_ref, process_queue_func):
    """Injeta dependências no blueprint de resumos."""
    global log_path, processar_fila_resumos
    log_path = log_path_ref
    processar_fila_resumos = process_queue_func


@resumo_bp.route('/resumo')
def resumo_index():
    """Renderiza a interface de resumo de vídeo"""
    logger.info("📋 Acessando página de resumo")
    
    fila_status = {
        'pending': SummaryQueue.query.filter_by(status='pending').count(),
        'completed': SummaryQueue.query.filter_by(status='completed').count(),
        'failed': SummaryQueue.query.filter_by(status='failed').count(),
        'paused': SummaryQueue.query.filter_by(status='paused').count()
    }
    
    return render_template('resumo.html', 
                          active_page='resumo',
                          fila_status=fila_status)
```

Veja o arquivo completo em `routes/resumo.py` para as outras 6 rotas.

---

## 🔧 ARQUIVO 3: Mudanças em `routes/__init__.py`

### ANTES:
```python
from routes.monitor import monitor_bp, setup_monitor_blueprint

__all__ = [
    'monitor_bp',
    'setup_monitor_blueprint',
]
```

### DEPOIS:
```python
from routes.monitor import monitor_bp, setup_monitor_blueprint
from routes.resumo import resumo_bp, setup_resumo_blueprint

__all__ = [
    'monitor_bp',
    'setup_monitor_blueprint',
    'resumo_bp',
    'setup_resumo_blueprint',
]
```

---

## 🔧 ARQUIVO 4: Mudanças em `app.py`

### MUDANÇA 1: Linha 19 (Import)

### ANTES:
```python
from routes import monitor_bp, setup_monitor_blueprint
```

### DEPOIS:
```python
from routes import monitor_bp, setup_monitor_blueprint, resumo_bp, setup_resumo_blueprint
```

---

### MUDANÇA 2: No bloco `__main__` (linhas ~484-490)

### ANTES:
```python
    # Setup e registro dos blueprints
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    app.register_blueprint(monitor_bp)
    logger.info("✅ Blueprint 'monitor_bp' registrado com sucesso")
    
    # Inicia o ouvinte de comandos do Telegram
    start_telegram_polling(app)
```

### DEPOIS:
```python
    # Setup e registro dos blueprints
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    app.register_blueprint(monitor_bp)
    logger.info("✅ Blueprint 'monitor_bp' registrado com sucesso")
    
    setup_resumo_blueprint(app, log_path, processar_fila_resumos)
    app.register_blueprint(resumo_bp)
    logger.info("✅ Blueprint 'resumo_bp' registrado com sucesso")
    
    # Inicia o ouvinte de comandos do Telegram
    start_telegram_polling(app)
```

---

## 🔧 ARQUIVO 5: Mudanças em `utils/__init__.py`

### ANTES:
```python
from utils.logging_config import setup_logging, NoPollingLogFilter
from utils.database_utils import inspect_and_migrate

__all__ = [
    'setup_logging',
    'NoPollingLogFilter',
    'inspect_and_migrate',
]
```

### DEPOIS:
```python
from utils.logging_config import setup_logging, NoPollingLogFilter
from utils.database_utils import inspect_and_migrate
from utils.helpers import get_api_url, build_api_endpoint, format_url

__all__ = [
    'setup_logging',
    'NoPollingLogFilter',
    'inspect_and_migrate',
    'get_api_url',
    'build_api_endpoint',
    'format_url',
]
```

---

## ✅ VALIDAÇÃO RÁPIDA

### Teste 1: Imports
```bash
python -c "from routes import resumo_bp; print('✅ Imports OK')"
python -c "from utils import get_api_url; print('✅ Helpers OK')"
```

### Teste 2: URLs
```bash
python -c "
from utils import get_api_url, build_api_endpoint
print(get_api_url('youtube'))
print(build_api_endpoint('/api/resumo', 'youtube'))
"
```

### Teste 3: App Inicia
```bash
python app.py
# Procure por: ✅ Blueprint 'resumo_bp' registrado com sucesso
```

### Teste 4: Rotas Acessíveis
```bash
# Em outro terminal:
curl http://localhost:5000/resumo
curl http://localhost:5000/api/fila/status
```

---

## 📊 RESUMO DE MUDANÇAS

| Arquivo | Tipo | Ação |
|---------|------|------|
| `utils/helpers.py` | ✅ NOVO | 3 funções: get_api_url, build_api_endpoint, format_url |
| `routes/resumo.py` | ✅ NOVO | 7 rotas: /resumo, /api/resumo, /api/archive-summary, /api/summarize-text, /add_to_queue_web, /api/fila/status, /api/fila/action |
| `routes/__init__.py` | 🔧 MODIFICADO | Adiciona exports de resumo_bp e setup_resumo_blueprint |
| `app.py` | 🔧 MODIFICADO | Adiciona import e registro do blueprint resumo_bp |
| `utils/__init__.py` | 🔧 MODIFICADO | Adiciona exports dos helpers |

---

## 🎯 STATUS

✅ **Todos os arquivos criados e modificados com sucesso!**

---

**Próximo passo:** Executar `python app.py` para confirmar 🚀
