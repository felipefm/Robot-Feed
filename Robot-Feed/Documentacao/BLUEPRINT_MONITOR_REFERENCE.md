# 📋 Referência: Blueprint Monitor

## Criação do Blueprint de Monitoramento

O blueprint `monitor_bp` foi criado com sucesso em `routes/monitor.py`.

---

## 📁 Estrutura

```
routes/
├── __init__.py ✅ (exports monitor_bp)
└── monitor.py ✅ (blueprint com as rotas)

app.py ✅ (registra o blueprint)
```

---

## 🚀 Rotas Movidas

Todas estas rotas foram movidas de `app.py` para `routes/monitor.py`:

| Rota | Método | Função | Status |
|------|--------|--------|--------|
| `/` | GET | `index()` | ✅ Movida |
| `/add_channel` | POST | `add_channel()` | ✅ Movida |
| `/toggle_mute/<id>` | GET | `toggle_mute(id)` | ✅ Movida |
| `/delete_channel/<id>` | GET | `delete_channel(id)` | ✅ Movida |
| `/force_check` | GET | `force_check()` | ✅ Movida |
| `/progress` | GET | `get_progress()` | ✅ Movida |
| `/logs` | GET | `view_logs()` | ✅ Movida |

---

## 💻 Uso no app.py

### Import
```python
from routes import monitor_bp, setup_monitor_blueprint
```

### Setup (antes de registrar o blueprint)
```python
# Injeta as dependências globais
setup_monitor_blueprint(app, log_path, check_feeds_with_context)
```

### Registração
```python
app.register_blueprint(monitor_bp)
```

### Exemplo Completo
```python
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        inspect_and_migrate()
        update_scheduler()
        # ... outros setups ...
    
    # Setup e registro dos blueprints
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    app.register_blueprint(monitor_bp)
    logger.info("✅ Blueprint 'monitor_bp' registrado com sucesso")
    
    # Inicia o app
    app.run(host='0.0.0.0', port=5000)
```

---

## 🔗 URLs das Rotas

As rotas continuam com os mesmos paths, mas agora pertencem ao blueprint:

| Endpoint | URL |
|----------|-----|
| **Página principal** | `GET /` |
| **Adicionar canal** | `POST /add_channel` |
| **Silenciar notificações** | `GET /toggle_mute/<id>` |
| **Deletar canal** | `GET /delete_channel/<id>` |
| **Forçar verificação** | `GET /force_check` |
| **Ver progresso** | `GET /progress` |
| **Ver logs** | `GET /logs` |

---

## 🔧 Como o Blueprint Funciona

### 1️⃣ **Injeção de Dependências**

Como o blueprint precisa de variáveis globais (`log_path` e `check_feeds_with_context`), usamos uma função de setup:

```python
# Em routes/monitor.py
log_path = None
check_feeds_with_context = None

def setup_monitor_blueprint(app, log_path_ref, check_feeds_func):
    """Injeta as dependências globais"""
    global log_path, check_feeds_with_context
    log_path = log_path_ref
    check_feeds_with_context = check_feeds_func
```

**Por quê?** Blueprints não têm acesso direto ao contexto global de `app.py`.

### 2️⃣ **Uso das Variáveis Injetadas**

Dentro das rotas:

```python
@monitor_bp.route('/logs')
def view_logs():
    # Usa a variável injetada
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            # ... lógica ...
```

### 3️⃣ **Redirects com url_for()**

As rotas usam `url_for()` com o nome do blueprint:

```python
# Antigo (app.py)
redirect(url_for('index'))

# Novo (routes/monitor.py)
redirect(url_for('monitor.index'))  # Nome do blueprint + função
```

---

## 📊 Comparação: Antes vs Depois

### Antes (app.py)
```python
# app.py tinha 1000+ linhas
# Linhas 142-282 tinham rotas de monitoramento aqui

@app.route('/')
def index():
    # ... 27 linhas ...

@app.route('/add_channel', methods=['POST'])
def add_channel():
    # ... 35 linhas ...

# ... mais 5 rotas aqui ...
```

### Depois

**app.py** (limpo)
```python
# Apenas 20 linhas de registro do blueprint
from routes import monitor_bp, setup_monitor_blueprint

if __name__ == '__main__':
    # ... setup ...
    setup_monitor_blueprint(app, log_path, check_feeds_with_context)
    app.register_blueprint(monitor_bp)
    # ... run app ...
```

**routes/monitor.py** (organizado)
```python
# Todas as rotas de monitoramento aqui
# +250 linhas bem estruturadas

@monitor_bp.route('/')
def index():
    # ... 27 linhas ...

@monitor_bp.route('/add_channel', methods=['POST'])
def add_channel():
    # ... 35 linhas ...

# ... mais 5 rotas aqui ...
```

---

## ✅ Checklist de Implementação

- [x] Blueprint `monitor_bp` criado em `routes/monitor.py`
- [x] 7 rotas movidas com sucesso
- [x] Função `setup_monitor_blueprint()` para injetar dependências
- [x] `routes/__init__.py` atualizado com exports
- [x] `app.py` atualizado com imports e registração
- [x] URLs mantêm mesmos paths (sem mudanças para o usuário)
- [x] Logging implementado em cada rota
- [x] Documentação completa

---

## 🐛 Troubleshooting

### Erro: "Endpoints have the same name"
**Causa:** Função registrada com mesmo nome em múltiplos blueprints  
**Solução:** Certifique-se que nomes de funções são únicos por blueprint

### Erro: "No module named 'routes'"
**Causa:** `routes/` não é um pacote Python  
**Solução:** Verifique se `routes/__init__.py` existe

### Erro: "log_path is None"
**Causa:** `setup_monitor_blueprint()` não foi chamada  
**Solução:** Adicione esta linha ANTES de `app.register_blueprint()`:
```python
setup_monitor_blueprint(app, log_path, check_feeds_with_context)
```

### Erro: "check_feeds_with_context is None"
**Causa:** Mesma causa acima  
**Solução:** Mesma solução acima

---

## 🎯 Próximas Etapas

### Fase 3: Criar Novos Blueprints

Seguindo o mesmo padrão:

```
routes/
├── __init__.py (exports todos)
├── monitor.py ✅ (monitoramento de canais)
├── config.py (rotas de configuração)
├── summary.py (rotas de resumo)
├── archive.py (rotas do cofre)
└── auction.py (rotas de leilões)
```

### Exemplo: Blueprint de Configuração

```python
# routes/config.py
from flask import Blueprint

config_bp = Blueprint('config', __name__)

@config_bp.route('/update_config', methods=['POST'])
def update_config():
    # ... lógica ...
    return redirect(url_for('config.update_config'))
```

---

## 📚 Referências

- [Flask Blueprints](https://flask.palletsprojects.com/en/latest/blueprints/)
- [url_for() com Blueprints](https://flask.palletsprojects.com/en/latest/blueprints/#building-urls)
- [Organizing Flask Apps](https://flask.palletsprojects.com/en/latest/blueprints/)

---

## 🎉 Conclusão

✅ **Blueprint Monitor criado com sucesso!**

**Benefícios:**
- ✅ `app.py` ~150 linhas mais limpo
- ✅ Código organizado e modular
- ✅ Fácil de testar
- ✅ Pronto para expandir com novos blueprints
- ✅ Sem mudança de URLs para o usuário final

**Próximo passo:** Criar `routes/config.py` com a rota `/update_config` 🚀
