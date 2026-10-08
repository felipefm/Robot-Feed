"""
cifras_scraper.py - Importação sob demanda de cifras do CifraClub (formato "simplificada").

Uso pessoal: busca UMA URL específica por vez, fornecida manualmente.
NÃO faz varredura de catálogo/listas do site — apenas a página informada.
"""

import re
import unicodedata
from html import unescape as _html_unescape

import requests
from bs4 import BeautifulSoup

# User-Agent identificável (não finge ser navegador). Ajuste o contato abaixo.
USER_AGENT = "RobotFeedCifras-Personal/1.0 (uso pessoal, contato: SEU_EMAIL_AQUI@exemplo.com)"

TIMEOUT = 10

_TAG_RE = re.compile(r"<[^>]+>")
_SECAO_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$")


class CifraScraperError(Exception):
    """Erro ao buscar ou interpretar uma cifra do CifraClub."""


def buscar_html_cifraclub(url: str) -> str:
    """
    Baixa o HTML de uma URL de cifra "simplificada" do CifraClub.

    Args:
        url (str): URL completa, ex.:
            https://www.cifraclub.com.br/<artista>/<musica>/simplificada.html

    Retorna:
        str: HTML da página

    Levanta:
        CifraScraperError: URL inválida, falha de rede ou status != 200
    """
    if not isinstance(url, str) or not url.strip():
        raise CifraScraperError("URL vazia.")

    url = url.strip()
    if not re.match(r"^https?://(www\.)?cifraclub\.com\.br/", url):
        raise CifraScraperError("A URL precisa ser de uma página do cifraclub.com.br.")

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise CifraScraperError(f"Falha de rede ao acessar o CifraClub: {e}") from e

    if resp.status_code != 200:
        raise CifraScraperError(
            f"O CifraClub respondeu com status {resp.status_code} para essa URL."
        )

    return resp.text


def parsear_cifra_simplificada(html: str) -> dict:
    """
    Extrai os dados de uma página "simplificada" do CifraClub.

    Args:
        html (str): HTML retornado por buscar_html_cifraclub()

    Retorna:
        dict: {
            'titulo': str,
            'artista': str | None,
            'tom_original': str | None,
            'capotraste': int | None,
            'linhas': [ {'acordes': str, 'letra': str} | {'secao': str}, ... ],
        }

    Levanta:
        CifraScraperError: se o bloco da cifra não for encontrado
    """
    soup = BeautifulSoup(html, "html.parser")

    titulo, artista = _extrair_titulo_artista(soup)

    # Tom: botão <button data-anchor="--chord-tone">C</button>
    tom_original = None
    btn_tom = soup.find("button", attrs={"data-anchor": "--chord-tone"})
    if btn_tom:
        tom_original = btn_tom.get_text(strip=True) or None

    capotraste = _extrair_capotraste(soup)

    # Bloco da cifra: <pre data-chord-content="true"> dentro de <article data-chord-container>
    pre = soup.find("pre", attrs={"data-chord-content": "true"})
    if pre is None:
        art = soup.find("article", attrs={"data-chord-container": "true"})
        pre = art.find("pre") if art else None
    if pre is None:
        raise CifraScraperError(
            "Não encontrei o bloco de cifra nesta página. "
            "Confira se a URL é da versão 'simplificada.html' de uma música."
        )

    linhas = _parsear_bloco_cifra(pre.decode_contents())
    if not linhas:
        raise CifraScraperError("O bloco de cifra foi encontrado, mas está vazio.")

    return {
        "titulo": titulo,
        "artista": artista,
        "tom_original": tom_original,
        "capotraste": capotraste,
        "linhas": linhas,
    }


def gerar_slug(titulo: str, artista: str) -> str:
    """
    Gera um slug "artista-titulo" em minúsculas, sem acento e com hífens.

    Args:
        titulo (str): Título da música
        artista (str): Artista (pode ser vazio/None)

    Retorna:
        str: ex. "legiao-urbana-tempo-perdido"
    """
    partes = [p for p in (artista, titulo) if p]
    base = "-".join(partes)
    base = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode("ascii")
    base = base.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base)
    return base.strip("-")


# --- helpers internos ---


def _texto_limpo(fragmento_html: str) -> str:
    """Remove tags e resolve entidades HTML de um fragmento, sem tocar nos espaços."""
    return _html_unescape(_TAG_RE.sub("", fragmento_html))


def _extrair_titulo_artista(soup):
    """Título/artista a partir de 'Titulo - Artista - Cifra Club' (og:title ou <title>)."""
    fonte = None
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        fonte = meta["content"]
    elif soup.title and soup.title.string:
        fonte = soup.title.string

    if not fonte:
        raise CifraScraperError("Não consegui identificar o título da música.")

    partes = [p.strip() for p in fonte.split(" - ") if p.strip()]
    if partes and partes[-1].lower().replace(" ", "") == "cifraclub":
        partes = partes[:-1]
    if not partes:
        raise CifraScraperError("Não consegui identificar o título da música.")

    titulo = partes[0]
    artista = partes[1] if len(partes) > 1 else None
    return titulo, artista


def _extrair_capotraste(soup):
    """Lê o rótulo 'Capotraste' e interpreta o valor ao lado ('Sem capotraste' / '2ª casa')."""
    rotulo = soup.find(string=re.compile(r"^\s*Capotraste\s*$"))
    if not rotulo:
        return None

    ancora = rotulo.find_parent()
    valor_el = ancora.find_next("p") if ancora else None
    texto = valor_el.get_text(" ", strip=True) if valor_el else ""

    if not texto or "sem capotraste" in texto.lower():
        return None

    m = re.search(r"\d+", texto)
    return int(m.group(0)) if m else None


def _parsear_bloco_cifra(inner_html: str):
    """
    Converte o HTML interno do <pre> em uma lista de blocos.

    Cada linha física (separada por '\\n') vira:
      - {'secao': 'Algo'}                 para marcadores [Algo]
      - {'acordes': <linha>, 'letra': ''} para linha de acordes (contém <b>) ou trecho instrumental
      - a linha de letra logo abaixo é anexada ao bloco de acordes anterior
    """
    # remove os wrappers <div>/<span>, preservando texto e quebras de linha originais
    corpo = re.sub(r"</?(?:div|span)[^>]*>", "", inner_html)

    blocos = []
    for bruto in corpo.split("\n"):
        tem_acorde = ("<b " in bruto) or ("<b>" in bruto)
        texto = _texto_limpo(bruto).rstrip()
        conteudo = texto.strip()
        if not conteudo:
            continue

        msec = _SECAO_RE.match(conteudo)
        if msec:
            blocos.append({"secao": msec.group(1).strip()})
            resto = re.sub(r"^\s*\[[^\]]+\]\s*", "", texto)
            if resto.strip():
                blocos.append({"acordes": resto, "letra": ""})
            continue

        if tem_acorde:
            blocos.append({"acordes": texto, "letra": None})
            continue

        # linha de letra: anexa à última linha de acordes ainda sem letra
        if blocos and blocos[-1].get("letra", "x") is None:
            blocos[-1]["letra"] = conteudo
        else:
            blocos.append({"acordes": "", "letra": conteudo})

    for b in blocos:
        if b.get("letra", "x") is None:
            b["letra"] = ""

    return blocos
