### 2. `CONTEXTO - PROJETO ROBOT FEED.md`

# 📑 Manual de Contexto: Projeto Robot Feed (Backend & Monitor)

### 1. Visão Geral e Propósito
O **Robot Feed** é um ecossistema de automação pessoal e "vigia digital". Ele liberta o usuário da necessidade de checar plataformas manualmente. O sistema monitora canais do YouTube (via RSS), busca lotes em sites de leilões e processa documentos longos para gerar resumos inteligentes.

### 2. Infraestrutura e Hardware
* **Servidor Principal:** Raspberry Pi rodando **CasaOS** (gerenciamento via Docker).
* **Processamento de IA (GPU Local):** PC Windows com **GPU AMD Radeon** rodando **LM Studio** (porta 1234). Utiliza modelos como Qwen 2.5 14B otimizados via Vulkan/ROCm.
* **Rede:** Comunicação via IP local entre o Raspberry (Backend) e o PC Windows (GPU).
* **Interface de Monitoramento:** Monitor 32" 4K (3840x2160) com escala de 125%.

### 3. Arquitetura Técnica (Backend FastAPI Modular)
O backend foi refatorado para evitar monólitos, dividindo responsabilidades através de `APIRouter`.
* **Estrutura Base (`app/`):** Separado em `core` (banco, roteador LLM), `services` (lógicas de scraping) e `api/routers` (endpoints específicos por domínio de negócio).
* **Inteligência Híbrida (Multi-LLM Router):** O sistema opera em cascata de fallback:
    1.  **TENTATIVA 1 (Local):** LM Studio (GPU Radeon).
    2.  **TENTATIVA 2 (Nuvem):** Google Gemini / Groq / DeepSeek / Mistral.
* **Processamento de Documentos:** Endpoints para extração de `PDF` (PyMuPDF/fitz) e `EPUB` (EbookLib). Possui limpeza de texto automática e função de **Split (Fatiamento)** para evitar estouro de VRAM na GPU local em textos longos.
* **Persistência:** Banco de dados **SQLite** (`cache_leilao.db`) gerido via `app/core/database.py` para histórico de lotes e cache.
* **Scrapers Assíncronos:** Motor de busca multithread (`asyncio` + `BeautifulSoup`) para leilões.

### 4. Interface e Interação (Bot Telegram & Web)
* **Voz do Sistema:** Bot do Telegram que envia notificações de novas Lives e recebe comandos para resumir vídeos ou textos.
* **Smart Live Cooldown:** Lógica que evita notificações repetitivas se uma live cair e voltar em curto intervalo.
* **Cofre (Vault):** Interface web onde os resumos processados e o status das lives são exibidos de forma organizada.

### 5. Diretrizes para Desenvolvimento (Prompt de Sistema)
* **Docker-First:** A aplicação roda em contêiner no CasaOS. **Atenção:** Qualquer alteração na estrutura de pastas (como a criação de novos modulos em `app/`) ou atualização de dependências exige um rebuild completo da imagem (`docker build --no-cache`).
* **Respeito ao Hardware:** O Raspberry Pi é o "cérebro" (coordena), mas a GPU local é o "músculo" (processa). Priorize códigos assíncronos (`async/await`) e `run_in_threadpool` para funções bloqueantes de I/O, garantindo que o servidor não trave.
* **Tratamento de Strings:** Sempre trate caracteres de controle (`\n`, `\t`) ao trafegar textos longos via JSON para evitar erros `422 Unprocessable Entity`.