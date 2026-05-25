# 📊 BLUEPRINT RESUMO: Resumo Visual com Diagramas

**Data:** 18 de Abril de 2026  
**Status:** ✅ **IMPLEMENTADO**

---

## 🎯 VISÃO GERAL

### Antes vs Depois

```
┌─────────────────────────────────┐       ┌──────────────────────────────────┐
│         ANTES                   │       │            DEPOIS                │
├─────────────────────────────────┤       ├──────────────────────────────────┤
│                                 │       │                                  │
│ app.py (1000+ linhas)           │       │ app.py (1000+ linhas)            │
│ ├─ Imports                      │       │ ├─ Imports                       │
│ ├─ Config                       │       │ ├─ Config                        │
│ ├─ 7 rotas monitor              │       │ ├─ (rotas monitor = blueprint)   │
│ ├─ 22 rotas leilão              │       │ ├─ (rotas leilão = blueprint)    │
│ ├─ ??? rotas resumo ❌          │       │ ├─ (rotas resumo = blueprint) ✅ │
│ ├─ Rotas utilidade              │       │ ├─ Rotas utilidade               │
│ ├─ API proxies                  │       │ ├─ API proxies                   │
│ └─ __main__                     │       │ └─ __main__                      │
│                                 │       │                                  │
└─────────────────────────────────┘       │ routes/                          │
                                          │ ├─ monitor.py ✅                 │
                                          │ ├─ resumo.py ✅ (NOVO)           │
                                          │ └─ __init__.py                   │
                                          │                                  │
                                          │ utils/                           │
                                          │ ├─ logging_config.py             │
                                          │ ├─ database_utils.py             │
                                          │ ├─ helpers.py ✅ (NOVO)          │
                                          │ └─ __init__.py                   │
                                          │                                  │
                                          └──────────────────────────────────┘
```

---

## 🏗️ ARQUITETURA DO BLUEPRINT RESUMO

```
┌────────────────────────────────────────────────────────────────┐
│                     BLUEPRINT RESUMO                           │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │                  PADRÃO DE INJEÇÃO                      │  │
│ │                                                          │  │
│ │  app.py __main__:                                       │  │
│ │  ├─ setup_resumo_blueprint(app, log_path, func)        │  │
│ │  └─ app.register_blueprint(resumo_bp)                  │  │
│ │                                                          │  │
│ │  routes/resumo.py:                                      │  │
│ │  ├─ resumo_bp = Blueprint('resumo')                    │  │
│ │  ├─ log_path = None (global)                           │  │
│ │  ├─ processar_fila_resumos = None (global)             │  │
│ │  └─ setup_resumo_blueprint() injeta as variáveis       │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │                    7 ROTAS                              │  │
│ │                                                          │  │
│ │  GET /resumo                   ────► Interface HTML    │  │
│ │  POST /api/resumo              ────► Gera resumo       │  │
│ │  POST /api/archive-summary     ────► Arquiva resumo    │  │
│ │  POST /api/summarize-text      ────► Sumariza texto    │  │
│ │  POST /add_to_queue_web        ────► Adiciona à fila   │  │
│ │  GET /api/fila/status          ────► Status da fila    │  │
│ │  POST /api/fila/action         ────► Gerencia fila     │  │
│ │                                                          │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌──────────────────────────────────────────────────────────┐  │
│ │              FUNÇÕES AUXILIARES (helpers)               │  │
│ │                                                          │  │
│ │  get_api_url(api_type)                                 │  │
│ │  ├─ Obtém URL da API do Config                        │  │
│ │  └─ Remove barra final automaticamente                │  │
│ │                                                          │  │
│ │  build_api_endpoint(path, api_type)                    │  │
│ │  ├─ Constrói URL completa                             │  │
│ │  └─ Evita duplas barras                               │  │
│ │                                                          │  │
│ │  format_url(url, **kwargs)                             │  │
│ │  └─ Formata URL com parâmetros                        │  │
│ │                                                          │  │
│ └──────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

---

## 🔄 FLUXO DE INTEGRAÇÃO

```
┌─────────────────────────────────────────────────────────────────────┐
│                    STARTUP (python app.py)                         │
└─────────────────────────────────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │ from routes import resumo_bp            │
        └─────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │ setup_resumo_blueprint(app,             │
        │   log_path,                             │
        │   processar_fila_resumos)               │
        │                                         │
        │ Injeta variáveis globais no blueprint  │
        └─────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │ app.register_blueprint(resumo_bp)       │
        │                                         │
        │ Registra todas as 7 rotas               │
        └─────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │ ✅ Blueprint 'resumo_bp' registrado     │
        │ Rotas disponíveis em:                   │
        │ ├─ /resumo                              │
        │ ├─ /api/resumo                          │
        │ ├─ /api/archive-summary                 │
        │ ├─ /api/summarize-text                  │
        │ ├─ /add_to_queue_web                    │
        │ ├─ /api/fila/status                     │
        │ └─ /api/fila/action                     │
        └─────────────────────────────────────────┘
```

---

## 📡 FLUXO DE UMA REQUISIÇÃO

```
┌──────────────┐
│ Cliente Web  │
└──────┬───────┘
       │
       │ POST /add_to_queue_web
       │ video_url=https://...
       ↓
┌─────────────────────────────┐
│ routes/resumo.py            │
│ add_to_queue_web()          │
│                             │
│ 1. Valida URL              │
│ 2. Verifica duplicata      │
│ 3. Cria SummaryQueue       │
│ 4. Chama processar_fila()  │
└──────────┬──────────────────┘
           │
           ├─────────────────────────────────────┐
           │                                     │
           ↓                                     ↓
    ┌─────────────────┐              ┌──────────────────────┐
    │  Banco de dados │              │  Backend de IA       │
    │  SummaryQueue   │              │  (http://host...)    │
    │                 │              │                      │
    │ CREATE:         │              │ POST /api/resumo     │
    │ - video_url     │              │ ↓                    │
    │ - status pending│              │ Processa vídeo       │
    │ - created_at    │              │ ↓                    │
    └────────┬────────┘              │ Retorna resumo       │
             │                       └──────────┬───────────┘
             │                                  │
             └──────────────┬───────────────────┘
                            │
                            ↓
                   ┌──────────────────────┐
                   │ VideoArchive         │
                   │                      │
                   │ INSERT/UPDATE:       │
                   │ - video_id           │
                   │ - title              │
                   │ - summary            │
                   │ - transcript         │
                   │ - tags               │
                   │ - archived_at        │
                   └──────────┬───────────┘
                              │
                              ↓
                   ┌──────────────────────┐
                   │ Resposta ao Cliente  │
                   │ {                    │
                   │   status: "success"  │
                   │   queue_item_id: 42  │
                   │ }                    │
                   └──────────────────────┘
```

---

## 🔗 INTEGRAÇÃO COM HELPERS

```
┌────────────────────────────────────────────────────────┐
│               utils/helpers.py                         │
├────────────────────────────────────────────────────────┤
│                                                        │
│  get_api_url('youtube')                              │
│  ├─ Config.youtube_api_url  ──┐                       │
│  └─ rstrip('/') ◄─────────────┘                       │
│     ↓                                                  │
│     'http://host.docker.internal:8000'               │
│                                                        │
│  get_api_url('auction')                              │
│  ├─ Config.auction_api_url ──┐                        │
│  └─ rstrip('/') ◄────────────┘                        │
│     ↓                                                  │
│     'http://192.168.0.6:8000'                         │
│                                                        │
│  build_api_endpoint('/api/resumo', 'youtube')        │
│  ├─ base_url = get_api_url('youtube')                │
│  ├─ path = 'api/resumo'                              │
│  └─ return f"{base_url}/{path}"                      │
│     ↓                                                  │
│     'http://host.docker.internal:8000/api/resumo'    │
│                                                        │
└────────────────────────────────────────────────────────┘
         ↑                                       ↑
         │ Usado em:                             │ Usado em:
         │ - routes/resumo.py                    │ - app.py (leilões)
         │ - feed_service.py (futuro)            │ - outras rotas
```

---

## 📈 ESTRUTURA DE BANCO DE DADOS

```
┌──────────────────────────────────────────────────┐
│             SummaryQueue (Fila)                  │
├──────────────────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY              │
│ video_url       VARCHAR(255) NOT NULL            │
│ status          VARCHAR(50) DEFAULT 'pending'    │
│                 [pending|processing|             │
│                  completed|failed|paused]        │
│ created_at      DATETIME DEFAULT UTC_NOW         │
├──────────────────────────────────────────────────┤
│ Exemplos de status:                              │
│ ├─ pending    → Aguardando processamento         │
│ ├─ processing → Sendo processado                 │
│ ├─ completed  → Sucesso, resumo gerado           │
│ ├─ failed     → Erro no processamento            │
│ └─ paused     → Pausado pelo usuário             │
└──────────────────────────────────────────────────┘
         ↓
         │ Após sucesso, dados transferem para:
         │
         ↓
┌──────────────────────────────────────────────────┐
│            VideoArchive (Cofre)                  │
├──────────────────────────────────────────────────┤
│ id              INTEGER PRIMARY KEY              │
│ channel_id      VARCHAR(50) NOT NULL             │
│ channel_name    VARCHAR(100) NOT NULL            │
│ video_id        VARCHAR(50) UNIQUE NOT NULL      │
│ title           VARCHAR(255) NOT NULL            │
│ published_at    VARCHAR(50)                      │
│ summary         TEXT                             │
│ full_transcript TEXT                             │
│ extracted_tags  VARCHAR(255)                     │
│ archived_at     DATETIME DEFAULT NOW             │
│ is_favorite     BOOLEAN DEFAULT FALSE            │
│ provider        TEXT (ex: "OpenAI")              │
│ tokens_used     INTEGER                          │
├──────────────────────────────────────────────────┤
│ Campos populados por:                            │
│ ├─ /api/resumo     ──► summary, transcript       │
│ ├─ /api/archive    ──► is_favorite               │
│ └─ /cofre (delete) ──► Delete row                │
└──────────────────────────────────────────────────┘
```

---

## 🎪 MATRIZ DE ROTAS

```
┌──────────────┬────────┬─────────────────────────┬────────────────┐
│ Rota         │ Método │ Função                  │ Tipo           │
├──────────────┼────────┼─────────────────────────┼────────────────┤
│ /resumo      │ GET    │ Interface web           │ Template (HTML)│
│              │        │                         │                │
│ /api/resumo  │ POST   │ Gera resumo (proxy)     │ JSON API       │
│              │        │ + Arquiva em VideoArchive               │
│              │        │                         │                │
│ /api/        │ POST   │ Arquiva resumo manual   │ JSON API       │
│ archive-     │        │ no Cofre                │                │
│ summary      │        │                         │                │
│              │        │                         │                │
│ /api/        │ POST   │ Sumariza texto (proxy)  │ JSON API       │
│ summarize-   │        │                         │                │
│ text         │        │                         │                │
│              │        │                         │                │
│ /add_to_     │ POST   │ Adiciona à fila         │ Formulário ou  │
│ queue_web    │        │ + Processa              │ JSON API       │
│              │        │                         │                │
│ /api/fila/   │ GET    │ Status da fila          │ JSON API       │
│ status       │        │ (pending, completed,    │                │
│              │        │  failed, paused)        │                │
│              │        │                         │                │
│ /api/fila/   │ POST   │ Ações na fila           │ JSON API       │
│ action       │        │ (pause, resume, remove) │                │
└──────────────┴────────┴─────────────────────────┴────────────────┘
```

---

## 📊 ESTATÍSTICAS

| Métrica | Valor |
|---------|-------|
| **Rotas criadas** | 7 |
| **Linhas de código (routes/resumo.py)** | ~450 |
| **Linhas de código (utils/helpers.py)** | ~65 |
| **Arquivos criados** | 2 |
| **Arquivos modificados** | 3 |
| **Funções auxiliares** | 3 |
| **Padrão de injeção** | ✅ Implementado |
| **Logging** | ✅ Completo |
| **Tratamento de erros** | ✅ Completo |

---

## ✅ CHECKLIST DE ESTRUTURA

```
✅ utils/helpers.py
   ├─ get_api_url()
   ├─ build_api_endpoint()
   └─ format_url()

✅ routes/resumo.py
   ├─ resumo_bp (Blueprint)
   ├─ setup_resumo_blueprint()
   ├─ @resumo_bp.route('/resumo')
   ├─ @resumo_bp.route('/api/resumo', methods=['POST'])
   ├─ @resumo_bp.route('/api/archive-summary', methods=['POST'])
   ├─ @resumo_bp.route('/api/summarize-text', methods=['POST'])
   ├─ @resumo_bp.route('/add_to_queue_web', methods=['POST'])
   ├─ @resumo_bp.route('/api/fila/status')
   └─ @resumo_bp.route('/api/fila/action', methods=['POST'])

✅ routes/__init__.py
   ├─ from routes.resumo import resumo_bp
   ├─ from routes.resumo import setup_resumo_blueprint
   └─ __all__ atualizado

✅ app.py
   ├─ from routes import resumo_bp, setup_resumo_blueprint
   ├─ setup_resumo_blueprint(app, log_path, processar_fila_resumos)
   ├─ app.register_blueprint(resumo_bp)
   └─ logger.info("✅ Blueprint 'resumo_bp' registrado")

✅ utils/__init__.py
   ├─ from utils.helpers import get_api_url
   ├─ from utils.helpers import build_api_endpoint
   ├─ from utils.helpers import format_url
   └─ __all__ atualizado
```

---

## 🚀 PRÓXIMAS ETAPAS

```
Phase 1 ✅ Refatoração (utils/)
├─ logging_config.py
└─ database_utils.py

Phase 2 ✅ Blueprints Monitor
└─ routes/monitor.py

Phase 3 ✅ Blueprints Resumo
├─ routes/resumo.py
└─ utils/helpers.py

Phase 4 ⏳ Blueprint Config
├─ routes/config.py
└─ Mover /update_config

Phase 5 ⏳ Blueprint Archive
├─ routes/archive.py
├─ /cofre
└─ /delete_cofre

Phase 6 ⏳ Blueprint Auction
├─ routes/auction.py
└─ Todas as rotas de leilão
```

---

**Status: ✅ COMPLETADO**

---

**Próximo:** Testar com `python app.py` 🚀
