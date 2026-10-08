# 📑 Manual de Contexto: Projeto Robot Feed (Backend & Monitor)

### 1. Visão Geral e Propósito
O **Robot Feed** é um ecossistema de automação pessoal e "vigia digital". Ele liberta o usuário da necessidade de checar plataformas manualmente. O sistema monitora canais do YouTube (via RSS), busca lotes em sites de leilões e processa documentos longos para gerar resumos inteligentes.

### 2. Infraestrutura e Hardware
* **Servidor Principal:** Raspberry Pi rodando **CasaOS** (gerenciamento via Docker).
* **Processamento de IA (GPU Local):** PC Windows com **GPU AMD Radeon** rodando **LM Studio** (porta 1234). Utiliza modelos como Qwen 2.5 14B otimizados via Vulkan/ROCm.
* **Rede:** Comunicação via IP local entre o Raspberry (Backend) e o PC Windows (GPU).
* **Interface de Monitoramento:** Monitor 32" 4K (3840x2160) com escala de 125%.

### 3. Arquitetura Técnica (Backend FastAPI)
* **Inteligência Híbrida (Multi-LLM Router):** O sistema opera em cascata de fallback:
    1.  **TENTATIVA 1 (Local):** LM Studio (GPU Radeon).
    2.  **TENTATIVA 2 (Nuvem):** Google Gemini (gemini-2.0-flash).
    3.  **TENTATIVA 3 (Nuvem):** Mistral AI (camada final de redundância).
* **Processamento de Documentos:** Endpoints para extração de `PDF` (PyMuPDF/fitz) e `EPUB` (EbookLib). Possui limpeza de texto automática e função de **Split (Fatiamento)** para evitar estouro de VRAM na GPU local em textos longos.
* **Persistência:** Banco de dados **SQLite** (`cache_leilao.db`) para histórico de lotes, termos de busca e cache de vídeos.
* **Scrapers:** Motor assíncrono (`asyncio` + `BeautifulSoup`) para múltiplos sites de leilão simultaneamente.

### 4. Interface e Interação (Bot Telegram & Web)
* **Voz do Sistema:** Bot do Telegram que envia notificações de novas Lives e recebe comandos para resumir vídeos ou textos.
* **Smart Live Cooldown:** Lógica que evita notificações repetitivas se uma live cair e voltar em curto intervalo.
* **Cofre (Vault):** Interface web onde os resumos processados e o status das lives são exibidos de forma organizada.

### 5. Diretrizes para Desenvolvimento (Prompt de Sistema)
* **Docker-First:** Qualquer alteração no código exige atualização do `requirements.txt` e rebuild da imagem (frequentemente com `--no-cache`).
* **Respeito ao Hardware:** O Raspberry Pi é o "cérebro" (coordena), mas a GPU local é o "músculo" (processa). Sugira sempre códigos assíncronos (`async/await`) para não bloquear o servidor.
* **Tratamento de Strings:** Sempre trate caracteres de controle (`\n`, `\t`) ao trafegar textos longos via JSON para evitar erros `422 Unprocessable Entity`.

