# 📋 REFERÊNCIA DE CÓDIGO: Blueprint Monitor

Documento com o código **exato** que deve estar em cada arquivo.

---

## 📄 Arquivo 1: routes/monitor.py

**Localização:** `Robot-Feed/routes/monitor.py`  
**Tamanho:** ~250 linhas  
**Status:** ✅ Criado

**Conteúdo esperado:**

```python
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
log_path = None
check_feeds_with_context = None


def setup_monitor_blueprint(app, log_path_ref, check_feeds_func):
    """
    Injeta dependências globais no blueprint.
    Deve ser chamado em app.py após criar o app e antes de registrar o blueprint.
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
            response = requests.get(f"{api_url}/get-channel-details/{identifier}", timeout=10)
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
            pass

        new_channel = Channel(name=name, channel_id=c_id, last_video_id=last_vid)
        db.session.add(new_channel)
        db.session.commit()
        logger.info(f"Novo canal adicionado: {name} ({c_id})")
        flash(f'Canal "{name}" adicionado com sucesso!', 'success')
    else:
        flash('Por favor, informe o identificador do canal.', 'error')
        
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
                channel.muted_live_id = None
                flash(f'Avisos reativados para a live atual de "{channel.name}".', 'success')
            else:
                channel.muted_live_id = channel.last_live_id
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
    
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r') as f:
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
    
    return jsonify(["Arquivo de log não encontrado."])
```

---

## 📄 Arquivo 2: routes/__init__.py

**Localização:** `Robot-Feed/routes/__init__.py`  
**Tamanho:** ~30 linhas  
**Status:** ✅ Modificado

**Conteúdo esperado:**

```python
"""
Blueprints de Rotas - Organização modular das rotas da aplicação.

Módulos:
    - monitor_bp: Rotas de monitoramento de canais ✅
    - (futuro) config_bp: Rotas de configuração
    - (futuro) summary_bp: Rotas de resumo de vídeos
    - (futuro) archive_bp: Rotas do Cofre de Conhecimento
    - (futuro) auction_bp: Rotas do sistema de Leilões

Exemplo de uso em app.py:
    from routes import monitor_bp, setup_monitor_blueprint
    
    # Setup de injeção de dependências
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    
    # Registrar blueprints
    app.register_blueprint(monitor_bp)
"""

from routes.monitor import monitor_bp, setup_monitor_blueprint

__all__ = [
    'monitor_bp',
    'setup_monitor_blueprint',
]
```

---

## 📄 Arquivo 3: app.py (Modificações)

**Localização:** `Robot-Feed/app.py`  
**Status:** ✅ Modificado

### Mudança 1: Adicionar Import

**Linha após:** `from utils import setup_logging, inspect_and_migrate`

**Adicionar:**
```python
from routes import monitor_bp, setup_monitor_blueprint
```

**Resultado esperado (linhas 17-20):**
```python
# Imports da estrutura modularizada
from utils import setup_logging, inspect_and_migrate
from routes import monitor_bp, setup_monitor_blueprint
```

---

### Mudança 2: Remover Rotas de Monitoramento

**Remover (aproximadamente linhas 142-282):**
```python
@app.route('/')
def index():
    # ... 27 linhas ...

@app.route('/add_channel', methods=['POST'])
def add_channel():
    # ... 35 linhas ...

@app.route('/toggle_mute/<int:id>')
def toggle_mute(id):
    # ... 25 linhas ...

@app.route('/delete_channel/<int:id>')
def delete_channel(id):
    # ... 7 linhas ...

@app.route('/update_config', methods=['POST'])
def update_config():
    # ... 25 linhas ... (❌ NÃO REMOVER ESTE - não foi solicitado)

@app.route('/force_check')
def force_check():
    # ... 9 linhas ...

@app.route('/progress')
def get_progress():
    # ... 3 linhas ...

@app.route('/logs')
def view_logs():
    # ... 15 linhas ...
```

---

### Mudança 3: Adicionar Registro do Blueprint

**Localizar:** `if __name__ == '__main__':`

**Antes:**
```python
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        inspect_and_migrate()
        update_scheduler()
        try:
            conf = get_config()
            if conf.telegram_token and conf.telegram_chat_id:
                send_telegram_message("🤖 Robot Feed: Sistema iniciado e monitorando!")
                logger.info("Mensagem de inicialização enviada.")
            else:
                logger.warning("Inicialização: Telegram não configurado. Aviso não enviado.")
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de inicialização: {e}")
    
    start_telegram_polling(app)
    app.run(host='0.0.0.0', port=5000)
```

**Depois:**
```python
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        inspect_and_migrate()
        update_scheduler()
        try:
            conf = get_config()
            if conf.telegram_token and conf.telegram_chat_id:
                send_telegram_message("🤖 Robot Feed: Sistema iniciado e monitorando!")
                logger.info("Mensagem de inicialização enviada.")
            else:
                logger.warning("Inicialização: Telegram não configurado. Aviso não enviado.")
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de inicialização: {e}")
    
    # ✅ NOVO: Setup e registro dos blueprints
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    app.register_blueprint(monitor_bp)
    logger.info("✅ Blueprint 'monitor_bp' registrado com sucesso")
    
    start_telegram_polling(app)
    app.run(host='0.0.0.0', port=5000)
```

---

## 📊 Resumo das Mudanças

| Arquivo | Tipo | Linhas | O quê |
|---------|------|--------|-------|
| `routes/monitor.py` | Criado | 250 | Blueprint com 7 rotas + setup |
| `routes/__init__.py` | Modificado | 30 | Exports do blueprint |
| `app.py` | Modificado | +3/-150 | Import + setup + registro do blueprint |

---

## ✅ Validação Rápida

Após fazer as mudanças, execute:

```bash
# 1. Verificar imports
python -c "from routes import monitor_bp, setup_monitor_blueprint; print('✅ OK')"

# 2. Verificar estrutura
python -c "import routes.monitor; print('✅ Módulo carrega')"

# 3. Verificar rotas
python -c "
from app import app
routes = [rule.rule for rule in app.url_map.iter_rules()]
print('✅ Rotas carregadas:', len(routes))
"
```

---

**Documento de referência concluído!**  
**Use este arquivo para copiar/colar o código exato necessário.**
