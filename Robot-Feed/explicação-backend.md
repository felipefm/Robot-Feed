# Backend - YouTube Live Status & Auction Scraper

## 🏗 Arquitetura Híbrida

Este projeto é um backend desenvolvido em **Python** utilizando o framework **FastAPI**. A arquitetura evoluiu para um modelo de **Inteligência Híbrida**, capaz de alternar entre processamento em **nuvem** e processamento **local** via GPU.

### Componentes Principais:
1.  **API Server (FastAPI):** Gerencia as requisições HTTP, validação de dados (Pydantic) e respostas assíncronas.
2.  **Multi-LLM Router:** 
    *TENTATIVA 1 (Local):* Tenta processar o resumo utilizando o LM Studio rodando modelos como Qwen 2.5 14B via rede local, aproveitando o poder de processamento de GPUs AMD/NVIDIA.

    *TENTATIVA 2 (Nuvem - Gemini):* Fallback automático para o Google Gemini (gemini-2.0-flash) caso o servidor local esteja offline ou ocupado.

    *TENTATIVA 3 (Nuvem - Mistral):* Última camada de redundância via API da Mistral AI.
3.  **Scraper Engine:**
    *   Utiliza `requests` e `BeautifulSoup` para extrair dados brutos de HTML.
    *   Implementa `asyncio` e `ThreadPoolExecutor` para realizar verificações em massa (batch) e buscas em múltiplos sites de leilão simultaneamente sem bloquear a thread principal.
4.  **Cache Layer (SQLite):**
    *   Para o módulo de Leilões, utiliza um banco de dados SQLite local (`cache_leilao.db`) para persistir resultados de buscas, evitando requisições repetitivas aos sites externos e mantendo histórico.
5.  **Integração Externa (Data Bridge):**
    *   Para o módulo de Resumos (Vídeos e Textos), o sistema não retém mais os dados localmente. O backend atua como um hub de processamento e envia automaticamente os resultados finais (JSON com metadados, métricas e transcrições) para uma API de arquivo no Frontend/Servidor Central via requisições HTTP `POST`.

---

## 🚀 Como Rodar

1.  Instale as dependências:
    ```bash
    pip install fastapi uvicorn requests beautifulsoup4 yt-dlp youtube-transcript-api google-generativeai mistralai openai python-dotenv
    ```
2.  Configure as variáveis de ambiente (necessário para o resumo de vídeos):
    * Crie um arquivo `.env` na raiz do projeto contendo sua chave do Google Gemini:
      ```env
        GEMINI_API_KEY="sua_chave_de_api_aqui"
        GEMINI_API_KEY="sua_chave"
        MISTRAL_API_KEY="sua_chave"
        OLLAMA_HOST_IP="192.168.0.2"  # IP do PC rodando LM Studio
        OLLAMA_MODEL="qwen2.5-14b-instruct-1m" # ID do modelo no LM Studio
      ```
3.  Execute o servidor:
    ```bash
    uvicorn main:app --reload
    ```
4.  Acesse a documentação interativa (Swagger UI):
    *   `http://127.0.0.1:8000/docs`

---

## 📡 Endpoints da API

### 📺 YouTube & Twitch (Live Status)

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/get-channel-details/{identifier}` | Retorna ID e Título de um canal (suporta Handle, ID ou URL). |
| `GET` | `/check-live/{channel_identifier}` | Verifica se um canal específico está ao vivo no momento. |
| `POST` | `/check-live-batch` | Verifica o status de múltiplos canais simultaneamente. <br>**Body:** `{"channel_ids": ["@canal1", "UC..."]}` |
| `GET` | `/get-live-duration` | Retorna a duração atual de uma live (tempo decorrido) baseada na URL do vídeo. |

### 📝 Resumo de Vídeos (Multi-LLM AI)

O endpoint de resumo agora é inteligente. Ele extrai a transcrição e decide qual modelo usar baseado na disponibilidade, priorizando sempre o custo zero do processamento local.

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `POST` | `/summarize-video` | Orquestra a transcrição e o resumo via LM Studio (Local), Gemini ou Mistral. <br>**Body:** `{"video_url": "URL"}` |
| `POST` | `/summarize-text` | Processa e resume textos inseridos manualmente utilizando o Roteador Multi-LLM. <br>**Body:** `{"title": "Título...", "text": "Texto completo..."}` |

### 🔨 Leilões (Auction Scraper)

O sistema busca em diversos sites de leilão (ex: RT Leilões, Sodré Santoro, etc.) e armazena em cache.

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `POST` | `/auction/search` | Realiza o scraping nos sites configurados para os termos informados. <br>**Body:** `{"terms": ["iphone", "ps5"]}` |
| `GET` | `/auction/history` | Retorna todo o histórico de itens encontrados e salvos no banco. |
| `GET` | `/auction/history/{termo}` | Retorna o histórico filtrado por um termo específico. |
| `DELETE` | `/auction/history` | **Delete All (Itens):** Remove todos os lotes do banco, mas mantém os termos cadastrados. |
| `DELETE` | `/auction/terms` | **Delete Terms:** <br>- Sem query param: Remove todos os termos e itens.<br>- Com `?termo=X`: Remove apenas o termo X e seus itens. |
| `DELETE` | `/auction/item/{item_id}` | **Delete Item:** Remove um item específico pelo ID do banco de dados. |

### 📦 Correios (Rastreamento)

Integração com API do SeuRastreio para consulta simplificada sem captcha.

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `POST` | `/correios/track` | Consulta direta do objeto usando o token configurado. <br>**Body:** `{"object_code": "NN110248660BR"}` |



---

## 🎵 Ferramentas Adicionais

### SoundCloud Downloader
Script CLI para baixar músicas do SoundCloud utilizando `yt-dlp`.

**Uso:**
```bash
python soundcloud_downloader.py "URL_DA_MUSICA"
# Opcional: --browser chrome (para usar cookies do navegador)
```