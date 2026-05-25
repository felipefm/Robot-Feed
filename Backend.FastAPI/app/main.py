"""
Robot Feed Backend - FastAPI Application
Arquitetura modular com routers organizados por funcionalidade.

Structure:
- app.core: Configuração, banco de dados, LLM router
- app.services: Lógica de negócio (scraping, etc)
- app.api.routers: Endpoints organizados por domínio
"""

import os
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

# Importação dos Roteadores Modulares
from app.api.routers.youtube import router as youtube_router
from app.api.routers.correios import router as correios_router
from app.api.routers.auctions import router as auctions_router
from app.api.routers.summarizer import router as summarizer_router
from app.api.routers.documents import router as documents_router

# Importação da Inicialização do Banco de Dados
from app.core.database import init_db

# ========== LOGGING ==========
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== INICIALIZAÇÃO DA API ==========
app = FastAPI(
    title="Robot Feed API",
    description="Backend modularizado para automação de feeds, monitoramento de lives, leilões e resumos com IA.",
    version="2.0.0"
)

# ========== MIDDLEWARE DE CORS ==========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== EVENTOS DE INICIALIZAÇÃO ==========
@app.on_event("startup")
def startup_event():
    try:
        init_db()
        logger.info("Banco de dados de leilões inicializado com sucesso.")
    except Exception as e:
        logger.error(f"Erro crítico ao inicializar o banco de dados: {e}")

# ========== INCLUSÃO DOS ROTEADORES MODULARES ==========
app.include_router(youtube_router)
app.include_router(correios_router)
app.include_router(auctions_router)
app.include_router(summarizer_router)
app.include_router(documents_router)

# ========== ENDPOINTS REMANESCENTES (ISAAC SHIELD & ROOT) ==========

@app.get("/isaac-shield/lista", tags=["Isaac Shield"])
def obter_lista_bloqueio():
    """
    Retorna a lista de canais/termos bloqueados para o script do Tampermonkey.
    Lê diretamente do arquivo 'canais_bloqueados.json'.
    """
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "canais_bloqueados.json")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "blocked_terms": [
                "felipe neto",
                "@felipeneto",
                "luccas neto",
                "@luccasneto"
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler a lista de bloqueios: {e}")

@app.get("/block-screen", response_class=HTMLResponse, include_in_schema=False)
def tela_de_bloqueio():
    """
    Serve a tela HTML customizada de bloqueio do IsaacShield.
    """
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "isaacshield_block.html")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "<body style='background:black; color:#ff4444; display:flex; justify-content:center; align-items:center; height:100vh; font-family:sans-serif; margin:0;'><h1>🔒 BLOQUEADO PELO SERVIDOR</h1></body>"

@app.get("/", include_in_schema=False)
async def root():
    return {"message": "Bem-vindo à API do Robot Feed. Acesse os endpoints documentados em /docs."}