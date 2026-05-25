"""
Router de Endpoints de Documentos
Extração de texto de PDF/EPUB e fatiamento inteligente de textos longos.
"""

import logging
import os
import re
import tempfile
from fastapi import APIRouter, HTTPException, File, UploadFile, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Dict, Any, List

import fitz  # PyMuPDF
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ========== MODELOS PYDANTIC ==========

class TextSplitRequest(BaseModel):
    """Requisição para dividir um texto longo."""
    text: str
    max_chars: int = 30000


# ========== ROUTER ==========

router = APIRouter(prefix="/api", tags=["Document Extraction"])


# ========== FUNÇÕES AUXILIARES ==========

def calculate_text_statistics(text: str) -> Dict[str, int]:
    """
    Calcula estatísticas sobre um texto (caracteres, palavras, parágrafos).
    
    Args:
        text: Texto a analisar
        
    Returns:
        Dicionário com:
        - characters: Total de caracteres
        - words: Total de palavras
        - paragraphs: Total de parágrafos (linhas não-vazias)
    """
    char_count = len(text)
    words = text.split()
    word_count = len(words)
    paragraphs = [p for p in text.split('\n') if p.strip()]
    
    return {
        "characters": char_count,
        "words": word_count,
        "paragraphs": len(paragraphs),
    }


def clean_extracted_text(text: str) -> str:
    """
    Limpa texto extraído de PDF/EPUB removendo caracteres especiais
    e normalizando espaçamento.
    
    Operações:
    1. Substitui escaped newlines/tabs por caracteres reais
    2. Remove múltiplas quebras de linha consecutivas
    3. Remove espaços múltiplos
    4. Remove linhas vazias duplicadas
    
    Args:
        text: Texto bruto extraído
        
    Returns:
        Texto limpo e normalizado
    """
    # 1. Substitui escaped characters por reais
    text = text.replace("\\n", "\n")
    text = text.replace("\\t", " ")
    text = text.replace("\\r", "")
    
    # 2. Remove múltiplas quebras de linha (mais de 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 3. Remove espaços múltiplos em cada linha
    lines = [line.strip() for line in text.split('\n')]
    cleaned_lines = []
    prev_empty = False
    
    for line in lines:
        if line == "":
            # Mantém apenas 1 linha vazia no máximo
            if not prev_empty:
                cleaned_lines.append(line)
            prev_empty = True
        else:
            cleaned_lines.append(line)
            prev_empty = False
    
    text = '\n'.join(cleaned_lines)
    
    # 4. Normaliza espaços horizontais múltiplos
    text = re.sub(r'[ \t]{2,}', ' ', text)
    
    return text.strip()


def process_pdf(file_content: bytes) -> str:
    """
    Extrai texto de um arquivo PDF.
    
    Args:
        file_content: Conteúdo binário do arquivo PDF
        
    Returns:
        Texto extraído de todas as páginas
        
    Raises:
        Exception: Se houver erro na leitura do PDF
    """
    doc = fitz.open(stream=file_content, filetype="pdf")
    text = ""
    
    for page_num, page in enumerate(doc, 1):
        page_text = page.get_text()
        text += page_text + "\n"
    
    logger.info(f"PDF processado: {doc.page_count} páginas, {len(text)} caracteres")
    
    return text.strip()


def process_epub(file_content: bytes) -> str:
    """
    Extrai texto de um arquivo EPUB.
    
    Nota: ebooklib requer arquivo físico, então usamos tempfile.
    
    Args:
        file_content: Conteúdo binário do arquivo EPUB
        
    Returns:
        Texto extraído de todos os documentos do eBook
        
    Raises:
        Exception: Se houver erro na leitura do EPUB
    """
    # ebooklib precisa de um caminho físico
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_file.write(file_content)
        temp_file_path = temp_file.name

    try:
        book = epub.read_epub(temp_file_path)
        text = ""
        items_count = 0
        
        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # Extrai HTML e converte para texto puro
                soup = BeautifulSoup(item.get_body_content(), 'html.parser')
                text += soup.get_text(separator='\n', strip=True) + "\n\n"
                items_count += 1
        
        logger.info(f"EPUB processado: {items_count} documentos, {len(text)} caracteres")
        
        return text.strip()
    finally:
        # Limpa arquivo temporário
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def split_long_text(text: str, max_chars: int = 30000) -> List[Dict[str, Any]]:
    """
    Divide um texto longo em blocos menores de forma inteligente.
    
    Estratégia de quebra (em ordem de preferência):
    1. Quebra de linha (\\n)
    2. Ponto final (.)
    3. Espaço em branco
    4. Corte forçado no limite
    
    Isso evita quebrar palavras no meio.
    
    Args:
        text: Texto a dividir
        max_chars: Tamanho máximo de cada bloco
        
    Returns:
        Lista de dicionários com:
        - bloco_numero: Número sequencial do bloco
        - conteudo: Conteúdo do bloco
    """
    chunks = []
    start = 0
    text_len = len(text)
    bloco_numero = 1
    
    while start < text_len:
        # Se o restante cabe em um bloco, adiciona e termina
        if text_len - start <= max_chars:
            chunk = text[start:].strip()
            if chunk:
                chunks.append({
                    "bloco_numero": bloco_numero,
                    "conteudo": chunk
                })
            break
        
        # Encontra o melhor ponto de corte
        end = start + max_chars
        
        # Tenta quebrar na última quebra de linha dentro do limite
        last_newline = text.rfind('\n', start, end)
        last_dot = text.rfind('.', start, end)
        last_space = text.rfind(' ', start, end)
        
        # Escolhe o melhor ponto de corte
        if last_newline != -1 and last_newline > start:
            cut_point = last_newline + 1
        elif last_dot != -1 and last_dot > start:
            cut_point = last_dot + 1
        elif last_space != -1 and last_space > start:
            cut_point = last_space + 1
        else:
            # Fallback: corte forçado
            cut_point = end
        
        # Adiciona o bloco
        chunk = text[start:cut_point].strip()
        if chunk:
            chunks.append({
                "bloco_numero": bloco_numero,
                "conteudo": chunk
            })
            bloco_numero += 1
        
        start = cut_point
    
    logger.info(f"Texto dividido em {len(chunks)} blocos")
    
    return chunks


# ========== ENDPOINTS ==========

@router.post(
    "/docs/extract-pdf",
    summary="Extrair Texto de PDF",
    description="Extrai todo o texto de um arquivo PDF e retorna em JSON ou TXT.",
)
async def extract_pdf_endpoint(
    file: UploadFile = File(...),
    format: str = Query(
        "json",
        description="Formato de saída: 'json' (padrão) ou 'txt'"
    ),
    split: bool = Query(
        False,
        description="Se True, retorna texto dividido em blocos numerados"
    ),
):
    """
    Extrai texto de um arquivo PDF.
    
    Args:
        file: Arquivo PDF a processar
        format: Formato de saída (json ou txt)
        split: Se True, divide em blocos de até 30000 caracteres
        
    Returns:
        - Se format=json (padrão): JSON com filename, text, statistics
        - Se format=txt: Arquivo de texto puro
        - Se split=True: Array de blocos numerados
        
    Raises:
        HTTPException 400: Arquivo não é PDF
        HTTPException 413: Arquivo muito grande
        
    Example:
        ```bash
        curl -F "file=@document.pdf" http://localhost/api/docs/extract-pdf
        curl -F "file=@document.pdf" "http://localhost/api/docs/extract-pdf?split=true"
        ```
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Tipo de arquivo inválido. Por favor envie um PDF.",
        )
    
    try:
        content = await file.read()
        text = await run_in_threadpool(process_pdf, content)
        text = clean_extracted_text(text)
        
        # Se solicitado, divide em blocos
        if split:
            return split_long_text(text)
        
        # Se solicitado formato TXT, retorna como arquivo
        if format.lower() == "txt":
            return Response(content=text, media_type="text/plain")
        
        # Padrão: retorna JSON com estatísticas
        stats = calculate_text_statistics(text)
        return {
            "filename": file.filename,
            "text": text,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar PDF: {e}",
        )


@router.post(
    "/docs/extract-epub",
    summary="Extrair Texto de EPUB",
    description="Extrai todo o texto de um arquivo EPUB e retorna em JSON ou TXT.",
)
async def extract_epub_endpoint(
    file: UploadFile = File(...),
    format: str = Query(
        "json",
        description="Formato de saída: 'json' (padrão) ou 'txt'"
    ),
    split: bool = Query(
        False,
        description="Se True, retorna texto dividido em blocos numerados"
    ),
):
    """
    Extrai texto de um arquivo EPUB (eBook).
    
    Args:
        file: Arquivo EPUB a processar
        format: Formato de saída (json ou txt)
        split: Se True, divide em blocos de até 30000 caracteres
        
    Returns:
        - Se format=json (padrão): JSON com filename, text, statistics
        - Se format=txt: Arquivo de texto puro
        - Se split=True: Array de blocos numerados
        
    Raises:
        HTTPException 400: Arquivo não é EPUB
        HTTPException 413: Arquivo muito grande
        
    Example:
        ```bash
        curl -F "file=@ebook.epub" http://localhost/api/docs/extract-epub
        curl -F "file=@ebook.epub" "http://localhost/api/docs/extract-epub?split=true"
        ```
    """
    if not file.filename.lower().endswith(".epub"):
        raise HTTPException(
            status_code=400,
            detail="Tipo de arquivo inválido. Por favor envie um EPUB.",
        )
    
    try:
        content = await file.read()
        text = await run_in_threadpool(process_epub, content)
        text = clean_extracted_text(text)
        
        # Se solicitado, divide em blocos
        if split:
            return split_long_text(text)
        
        # Se solicitado formato TXT, retorna como arquivo
        if format.lower() == "txt":
            return Response(content=text, media_type="text/plain")
        
        # Padrão: retorna JSON com estatísticas
        stats = calculate_text_statistics(text)
        return {
            "filename": file.filename,
            "text": text,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao processar EPUB: {e}",
        )


@router.post(
    "/docs/split-text",
    summary="Dividir Texto Longo",
    description=(
        "Divide um texto longo em blocos menores de forma inteligente, "
        "sem quebrar palavras ou frases."
    ),
)
async def split_text_endpoint(request: TextSplitRequest):
    """
    Divide um texto em blocos menores mantendo coesão.
    
    Estratégia:
    1. Tenta quebrar em última quebra de linha (\\n)
    2. Se não houver, tenta último ponto final (.)
    3. Se não houver, tenta último espaço
    4. Última opção: corte forçado no limite
    
    Args:
        request: TextSplitRequest com text e max_chars (padrão 30000)
        
    Returns:
        Lista de blocos numerados com conteúdo
        
    Example:
        ```json
        {
            "text": "Lorem ipsum dolor sit amet...",
            "max_chars": 50000
        }
        ```
        
        Retorna:
        ```json
        [
            {"bloco_numero": 1, "conteudo": "Lorem ipsum..."},
            {"bloco_numero": 2, "conteudo": "Dolor sit..."},
            ...
        ]
        ```
    """
    if not request.text or len(request.text.strip()) == 0:
        raise HTTPException(
            status_code=400,
            detail="Texto não pode estar vazio.",
        )
    
    if request.max_chars < 1000:
        raise HTTPException(
            status_code=400,
            detail="max_chars deve ser pelo menos 1000.",
        )
    
    try:
        blocks = split_long_text(request.text, request.max_chars)
        return blocks
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao dividir texto: {e}",
        )
