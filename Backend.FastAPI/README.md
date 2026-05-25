# Backend - YouTube Live Status & Auction Scraper

## 🏗 Arquitetura Híbrida e Modular

Este projeto é um backend desenvolvido em **Python** utilizando o framework **FastAPI**. A arquitetura evoluiu para um modelo de **Inteligência Híbrida** (alternando entre nuvem e processamento local) e foi refatorada para um **padrão modular** utilizando `APIRouter`, garantindo escalabilidade e facilidade de manutenção.

### Estrutura do Projeto:
A aplicação está organizada no diretório `app/`:
* `app/main.py`: Ponto de entrada, configuração de CORS e registro de roteadores.
* `app/core/`: Configurações centrais, conexão com banco de dados (`database.py`) e roteamento de inteligência artificial (`llm_router.py`).
* `app/services/`: Motores de scraping (YouTube, Correios, Leilões) e processamento de documentos (PDF/EPUB).
* `app/api/routers/`: Endpoints isolados por domínio (YouTube, Leilões, Resumos, Documentos, Correios).

### Componentes Principais:
1.  **Multi-LLM Router:** *TENTATIVA 1 (Local):* Tenta processar o resumo utilizando o LM Studio rodando modelos como Qwen 2.5 14B via rede local, aproveitando o poder de processamento de GPUs AMD/NVIDIA.
    *TENTATIVA 2 (Nuvem - Gemini):* Fallback automático para o Google Gemini (gemini-2.0-flash) caso o servidor local esteja offline ou ocupado.
    *TENTATIVA 3 (Nuvem - Mistral):* Última camada de redundância via API da Mistral AI.
2.  **Scraper Engine:**
    * Utiliza `requests` e `BeautifulSoup` para extrair dados brutos de HTML.
    * Implementa `asyncio` e `ThreadPoolExecutor` para verificações em massa e buscas paralelas.
3.  **Cache Layer (SQLite):**
    * Utiliza um banco local (`cache_leilao.db`) para persistir resultados de buscas de leilão, evitando bloqueios por excesso de requisições.
4.  **Integração Externa (Data Bridge):**
    * O backend atua como hub, processando resumos de vídeos/textos e enviando o JSON final (com metadados e transcrições) para a API do Frontend/Servidor Central.

---

## 🚀 Como Rodar

1.  Instale as dependências:
    ```bash
    pip install fastapi uvicorn requests beautifulsoup4 yt-dlp youtube-transcript-api google-generativeai mistralai openai python-dotenv PyMuPDF EbookLib
    ```
2.  Configure as variáveis de ambiente (necessário para o resumo de vídeos):
    * Crie um arquivo `.env` na raiz do projeto:
      ```env
        GEMINI_API_KEY="sua_chave_de_api_aqui"
        MISTRAL_API_KEY="sua_chave"
        DEEPSEEK_API_KEY="sua_chave"
        GROQ_API_KEY="sua_chave"
        OLLAMA_HOST_IP="192.168.0.2"  # IP do PC rodando LM Studio
        OLLAMA_MODEL="qwen2.5-14b-instruct-1m" # ID do modelo no LM Studio
      ```
3.  Execute o servidor (Atenção ao novo caminho do módulo):
    ```bash
    uvicorn app.main:app --reload
    ```
4.  Acesse a documentação interativa (Swagger UI):
    * `http://127.0.0.1:8000/docs`

---

## 📡 Endpoints da API

A documentação completa pode ser testada nativamente no Swagger UI. Abaixo estão as categorias principais geridas pelos roteadores modulares:

* **YouTube & Twitch (`/app/api/routers/youtube.py`):** Status de lives, detalhes de canais e duração de transmissões.
* **Video & Text Summary (`/app/api/routers/summarizer.py`):** Resumo inteligente via Multi-LLM para vídeos do YouTube e textos avulsos.
* **Auctions (`/app/api/routers/auctions.py`):** Motor de busca em dezenas de sites de leilão, salvamento em cache e histórico local.
* **Correios (`/app/api/routers/correios.py`):** Rastreio de encomendas contornando captchas via integração externa.
* **Document Extraction (`/app/api/routers/documents.py`):** Processamento, extração e fatiamento inteligente de arquivos PDF e EPUB.
* **Isaac Shield:** Gerenciamento da lista de canais bloqueados e tela de bloqueio do monitor digital.

---

## 🎵 Ferramentas Adicionais

### SoundCloud Downloader
Script CLI para baixar músicas do SoundCloud utilizando `yt-dlp`.

**Uso:**
```bash
python soundcloud_downloader.py "URL_DA_MUSICA"
# Opcional: --browser chrome (para usar cookies do navegador)