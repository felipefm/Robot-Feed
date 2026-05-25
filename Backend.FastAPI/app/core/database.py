"""
Módulo de Banco de Dados - SQLite para Leilões
Responsável por toda a lógica de persistência de leilões.
"""

import sqlite3
import time
import random
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel
import concurrent.futures

# ========== MODELOS PYDANTIC ==========

class AuctionItem(BaseModel):
    """Modelo para um item de leilão retornado nas buscas."""
    titulo: str
    link: str
    imagem: str
    valor: str
    lances: int
    data_leilao: str


class AuctionSearchRequest(BaseModel):
    """Modelo para requisição de busca de leilões."""
    terms: List[str]


class AuctionHistoryItem(BaseModel):
    """Modelo para item no histórico de leilões salvo em banco de dados."""
    id: int
    termo: str
    site: str
    titulo: str
    link: str
    imagem: str
    valor: str
    lances: int
    data_leilao: str


# ========== CONSTANTES ==========

LEILAO_URLS = [
    "https://www.rtleiloes.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.bruceangeirasleiloeiro.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.estilousado.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.canelaantiguidades.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.evanioalvesleiloeiro.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.letravivaleiloes.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.tratofeitobrazilleiloes.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.anamelloleiloeira.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.conradoleiloeiro.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.prochicleiloes.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.rosanavaleleiloes.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.gabrielamartinsleiloeira.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.pascavalcante.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1",
    "https://www.tamiriscarvalholeiloeira.com.br/pesquisa.asp?p=on&pesquisa={termo}&Ativo=1"
]

logger = logging.getLogger(__name__)


# ========== FUNÇÕES DE INICIALIZAÇÃO E GERENCIAMENTO DO BANCO ==========

def init_db() -> None:
    """Inicializa o banco de dados SQLite com as tabelas de leilões."""
    conn = sqlite3.connect('cache_leilao.db', timeout=10)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS termos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            nome TEXT NOT NULL UNIQUE
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS lotes_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            termo_id INTEGER, 
            dominio TEXT, 
            titulo TEXT, 
            link TEXT,
            imagem TEXT, 
            valor TEXT, 
            lances INTEGER, 
            data_leilao TEXT,
            FOREIGN KEY (termo_id) REFERENCES termos (id)
        )
    ''')
    
    c.execute('''
        CREATE UNIQUE INDEX IF NOT EXISTS idx_lote_unico 
        ON lotes_cache (termo_id, dominio, link)
    ''')
    
    conn.commit()
    conn.close()


def salvar_cache_sqlite(termo: str, dominio: str, lotes: List[Dict[str, Any]]) -> None:
    """
    Salva ou atualiza itens de leilão no banco de dados SQLite com tratamento de lock.
    
    Args:
        termo: Termo de busca
        dominio: Domínio do site de leilão
        lotes: Lista de dicionários com dados dos lotes
    """
    retries = 4
    for i in range(retries):
        try:
            conn = sqlite3.connect('cache_leilao.db', timeout=10)
            c = conn.cursor()
            
            # Insere ou ignora o termo
            c.execute('INSERT OR IGNORE INTO termos (nome) VALUES (?)', (termo,))
            c.execute('SELECT id FROM termos WHERE nome = ?', (termo,))
            
            termo_id_result = c.fetchone()
            if not termo_id_result:
                conn.close()
                return
            
            termo_id = termo_id_result[0]

            for lote in lotes:
                lances = lote.get('lances', 0)
                try:
                    lances = int(lances)
                except (ValueError, TypeError):
                    lances = 0
                
                data_leilao = lote.get('data_leilao', '') or ''
                
                c.execute('''
                    INSERT INTO lotes_cache (termo_id, dominio, titulo, link, imagem, valor, lances, data_leilao)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(termo_id, dominio, link) DO UPDATE SET
                        valor=excluded.valor, lances=excluded.lances, data_leilao=excluded.data_leilao,
                        titulo=excluded.titulo, imagem=excluded.imagem
                    WHERE valor != excluded.valor OR lances != excluded.lances
                ''', (termo_id, dominio, lote.get('titulo', ''), lote.get('link', ''), 
                      lote.get('imagem', ''), lote.get('valor', ''), lances, data_leilao))
            
            conn.commit()
            conn.close()
            return
            
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e) and i < retries - 1:
                time.sleep(random.uniform(0.2, 0.8))
                continue
            else:
                logger.error(f"Erro ao salvar cache SQLite (tentativa {i+1}): {e}")
                return
        except Exception as e:
            logger.error(f"Erro inesperado ao salvar cache: {e}")
            return


def buscar_cache_sqlite(termo: str, dominio: str) -> List[Dict[str, Any]]:
    """
    Busca itens em cache para um termo e domínio específicos.
    
    Args:
        termo: Termo de busca
        dominio: Domínio do site
        
    Returns:
        Lista de lotes em cache
    """
    conn = sqlite3.connect('cache_leilao.db', timeout=10)
    c = conn.cursor()
    
    c.execute('''
        SELECT l.titulo, l.link, l.imagem, l.valor, l.lances, l.data_leilao 
        FROM lotes_cache l
        JOIN termos t ON l.termo_id = t.id 
        WHERE t.nome=? AND l.dominio=?
    ''', (termo, dominio))
    
    rows = c.fetchall()
    conn.close()
    
    return [
        {
            'titulo': r[0], 
            'link': r[1], 
            'imagem': r[2], 
            'valor': r[3], 
            'lances': r[4], 
            'data_leilao': r[5]
        } 
        for r in rows
    ]


def list_auctions_db(termo: str = None) -> List[Dict[str, Any]]:
    """
    Lista todos os leilões do banco de dados, opcionalmente filtrado por termo.
    
    Args:
        termo: Termo opcional para filtro
        
    Returns:
        Lista de itens de leilão com todos os detalhes
    """
    conn = sqlite3.connect('cache_leilao.db', timeout=10)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    sql = '''
        SELECT l.id, t.nome as termo, l.dominio as site, l.titulo, l.link, 
               l.imagem, l.valor, l.lances, l.data_leilao 
        FROM lotes_cache l
        JOIN termos t ON l.termo_id = t.id
    '''
    
    params = []
    if termo:
        sql += ' WHERE t.nome LIKE ?'
        params.append(f'%{termo}%')
    
    sql += ' ORDER BY l.id DESC'
    
    c.execute(sql, tuple(params))
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


def delete_all_lotes_db() -> None:
    """Remove todos os itens de leilão (lotes) do banco de dados."""
    conn = sqlite3.connect('cache_leilao.db', timeout=10)
    c = conn.cursor()
    c.execute('DELETE FROM lotes_cache')
    conn.commit()
    conn.close()


def delete_termo_db(termo: str = None) -> None:
    """
    Remove um termo específico e seus lotes associados, ou todos se termo for None.
    
    Args:
        termo: Termo a remover, ou None para remover todos
    """
    conn = sqlite3.connect('cache_leilao.db', timeout=10)
    c = conn.cursor()
    
    if termo:
        c.execute('SELECT id FROM termos WHERE nome = ?', (termo,))
        row = c.fetchone()
        if row:
            termo_id = row[0]
            c.execute('DELETE FROM lotes_cache WHERE termo_id = ?', (termo_id,))
            c.execute('DELETE FROM termos WHERE id = ?', (termo_id,))
    else:
        c.execute('DELETE FROM lotes_cache')
        c.execute('DELETE FROM termos')
    
    conn.commit()
    conn.close()


def delete_auction_item_db(item_id: int) -> bool:
    """
    Remove um item de leilão específico pelo ID.
    
    Args:
        item_id: ID do item a remover
        
    Returns:
        True se o item foi removido, False caso contrário
    """
    conn = sqlite3.connect('cache_leilao.db', timeout=10)
    c = conn.cursor()
    c.execute('DELETE FROM lotes_cache WHERE id = ?', (item_id,))
    conn.commit()
    deleted = c.rowcount > 0
    conn.close()
    return deleted


# ========== FUNÇÕES AUXILIARES DE PARSING ==========

def _get_max_pag(soup: BeautifulSoup) -> int:
    """
    Extrai o número máximo de páginas do HTML.
    
    Args:
        soup: BeautifulSoup object do HTML
        
    Returns:
        Número máximo de páginas (padrão 1)
    """
    matches = []
    for a in soup.find_all('a', href=True):
        m = re.search(r'[?&]pag=(\d+)', a['href'])
        if m:
            matches.append(int(m.group(1)))
    return max(matches) if matches else 1


def _extrair_data_leilao(lote_soup: BeautifulSoup) -> str:
    """
    Extrai a data de encerramento do leilão do HTML do lote.
    
    Args:
        lote_soup: BeautifulSoup object do lote
        
    Returns:
        Data no formato YYYY-MM-DD ou string vazia
    """
    textos = []
    
    # Tenta extrair de meta tags
    for prop in ['product:expiration_date', 'og:title', 'og:description']:
        meta = lote_soup.find('meta', attrs={'property': prop})
        if meta and meta.has_attr('content'):
            textos.append(meta['content'])
    
    # Tenta extrair de tags HTML
    for tag in lote_soup.find_all(['span', 'p', 'div']):
        textos.append(tag.get_text())
    
    # Procura por padrões de data
    for texto in textos:
        if not texto:
            continue
        
        # Formato YYYY-MM-DD
        m = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', texto)
        if m:
            try:
                return datetime(*map(int, m.groups())).strftime('%Y-%m-%d')
            except ValueError:
                continue
        
        # Formato DD/MM/YYYY
        m = re.search(r'(\d{1,2})/(\d{1,2})/(\d{4})', texto)
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime('%Y-%m-%d')
            except ValueError:
                continue
    
    return ''


def _extrair_valor_lances(lote_soup: BeautifulSoup) -> tuple[str, int]:
    """
    Extrai o valor atual e número de lances do lote.
    
    Args:
        lote_soup: BeautifulSoup object do lote
        
    Returns:
        Tupla (valor, lances)
    """
    valor, lances = '', 0
    
    # Tenta extrair valor
    valor_tag = lote_soup.find('li', class_='valor-atual')
    if valor_tag:
        valor_span = valor_tag.find('span', class_='is-valor')
        if valor_span:
            valor = valor_span.get_text(strip=True)
    
    # Tenta extrair número de lances
    for p in lote_soup.find_all('p'):
        label = p.find('label')
        if label and 'Histórico de lances' in label.get_text():
            m = re.search(r'(\d+)\s*lance', p.get_text())
            if m:
                lances = int(m.group(1))
            break
    
    return valor, lances


def _processar_lote(lote_html: BeautifulSoup, pag_url: str) -> Dict[str, Any]:
    """
    Processa um elemento HTML de lote extraindo todas as informações.
    
    Args:
        lote_html: BeautifulSoup object do lote
        pag_url: URL da página para links relativos
        
    Returns:
        Dicionário com dados do lote
    """
    # Extrai imagem
    img_tag = lote_html.find('img')
    img_src = img_tag['src'] if img_tag else ''
    
    # Extrai título e link
    prod_title = lote_html.find('div', class_='prod-title')
    a_title = prod_title.find('a', href=True) if prod_title else None
    titulo = a_title.get_text(strip=True) if a_title else lote_html.get_text(strip=True)
    link = a_title['href'] if a_title and a_title.has_attr('href') else pag_url
    
    valor, lances = _extrair_valor_lances(lote_html)
    data_leilao = _extrair_data_leilao(lote_html)
    lote_link = link if link.startswith('http') else pag_url

    # Se faltam informações críticas, busca na página de detalhe
    if not valor or lances == 0 or not data_leilao:
        try:
            detalhe_resp = requests.get(lote_link, timeout=10)
            detalhe_resp.raise_for_status()
            detalhe_soup = BeautifulSoup(detalhe_resp.text, 'html.parser')
            valor, lances = _extrair_valor_lances(detalhe_soup)
            data_leilao = _extrair_data_leilao(detalhe_soup)
        except requests.RequestException:
            pass

    return {
        'titulo': titulo,
        'link': lote_link,
        'imagem': img_src if img_src.startswith('http') else pag_url + '/' + img_src,
        'valor': valor,
        'lances': lances,
        'data_leilao': data_leilao
    }


# ========== FUNÇÕES PRINCIPAIS DE BUSCA ==========

def buscar_lotes(url: str, termo: str) -> List[Dict[str, Any]]:
    """
    Busca lotes em um site de leilão, usando cache quando disponível.
    
    Args:
        url: URL do site de busca
        termo: Termo de busca
        
    Returns:
        Lista de lotes encontrados
    """
    dominio = urlparse(url).netloc.replace('.', '_')
    
    # Tenta buscar do cache primeiro
    cache_lotes = buscar_cache_sqlite(termo, dominio)
    if cache_lotes:
        return cache_lotes
    
    resultados = []
    
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        max_pag = _get_max_pag(soup)
        
        # Prepara URLs de paginação
        pag_urls = [url]
        for p in range(2, max_pag + 1):
            if '&pag=' in url or '?pag=' in url:
                url_base = re.sub(r'([&?]pag=\d+)', '', url)
            else:
                url_base = url
            sep = '&' if '?' in url_base else '?'
            pag_urls.append(f"{url_base}{sep}pag={p}")
        
        # Processa cada página com thread pool
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            for pag_url in pag_urls:
                try:
                    if pag_url != url:
                        resp = requests.get(pag_url, timeout=10)
                        resp.raise_for_status()
                        soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    lotes = soup.find_all('li', class_='four columns')
                    futures = [executor.submit(_processar_lote, lote, pag_url) for lote in lotes]
                    
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            resultados.append(future.result())
                        except Exception:
                            pass
                except Exception:
                    pass

        # Fallback: tenta extrair via imagens se não achou lotes estruturados
        if not resultados:
            for img in soup.find_all('img'):
                alt = img.get('alt', '').strip()
                src = img.get('src', '')
                parent = img.find_parent('a')
                link = parent['href'] if parent and parent.has_attr('href') else url
                
                if alt and link and src and 'logo' not in src and 'banner' not in src:
                    resultados.append({
                        'titulo': alt,
                        'link': link if link.startswith('http') else url,
                        'imagem': src if src.startswith('http') else url + '/' + src,
                        'valor': '', 
                        'lances': 0, 
                        'data_leilao': ''
                    })

    except requests.RequestException as e:
        logger.error(f"Erro ao buscar lotes em {url}: {e}")

    # Salva no cache se encontrou resultados
    if resultados:
        try:
            salvar_cache_sqlite(termo, dominio, resultados)
        except Exception as e:
            logger.error(f"Erro ao salvar cache para {termo} em {dominio}: {e}")
    
    return resultados
