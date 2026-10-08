"""
routes/cifras.py - Blueprint para o módulo de Cifras (acordes e letras)
Página de busca/listagem e visualização de músicas com dados para transposição de tom.
"""

import json
import logging
import os
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, abort, send_from_directory
from extensions import db
from models import Musica

logger = logging.getLogger(__name__)

# Criar blueprint
cifras_bp = Blueprint('cifras', __name__)

# Raiz do projeto (um nível acima de routes/), para servir arquivos estáticos próprios
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))

# Variáveis globais que serão injetadas
log_path = None
data_dir = None


def setup_cifras_blueprint(app, data_dir_ref):
    """
    Injeta dependências no blueprint de cifras.

    Args:
        app (Flask): Aplicação Flask
        data_dir_ref (str): Caminho para o diretório de dados (fonte futura das cifras)
    """
    global data_dir
    data_dir = data_dir_ref


# --- CARREGAMENTO E PERSISTÊNCIA DE DADOS ---


def _carregar_musica(slug):
    """
    Carrega os dados de uma música pelo slug, a partir da tabela `musica`.

    Reconstitui os blocos (acordes + letra) via json.loads(musica.conteudo).
    Mantém o mesmo formato de dicionário consumido hoje pelas rotas/templates.

    Args:
        slug (str): Identificador da música na URL

    Retorna:
        dict | None: Dados da música ou None se não encontrada
    """
    logger.info(f"🎸 Carregando música: {slug}")

    musica = Musica.query.filter_by(slug=slug).first()
    if not musica:
        return None

    blocos = json.loads(musica.conteudo)

    # Lista de acordes únicos (na ordem de aparição) extraída dos blocos
    acordes = []
    for bloco in blocos:
        for token in (bloco.get('acordes') or '').split():
            if token not in acordes:
                acordes.append(token)

    return {
        'slug': musica.slug,
        'titulo': musica.titulo,
        'artista': musica.artista,
        'tom': musica.tom_original,
        'capotraste': musica.capotraste,
        'acordes': acordes,
        'linhas': blocos,
    }


def salvar_musica(slug, titulo, artista, tom_original, blocos, capotraste=None):
    """
    Upsert de uma música na tabela `musica`.

    Serializa a lista de blocos (acordes + letra) em JSON no campo `conteudo`.
    Se já existir um registro com o mesmo slug, atualiza; senão, cria.

    Ainda não é chamada por nenhuma rota - uso manual / futuro scraper.

    Args:
        slug (str): Identificador único da música
        titulo (str): Título da música
        artista (str | None): Artista
        tom_original (str | None): Tom original
        blocos (list): Lista de dicts no formato {'acordes': str, 'letra': str}
        capotraste (int | None): Casa do capotraste

    Retorna:
        Musica: registro salvo
    """
    conteudo = json.dumps(blocos, ensure_ascii=False)

    musica = Musica.query.filter_by(slug=slug).first()
    if musica:
        musica.titulo = titulo
        musica.artista = artista
        musica.tom_original = tom_original
        musica.capotraste = capotraste
        musica.conteudo = conteudo
        logger.info(f"🎸 Música atualizada: {slug}")
    else:
        musica = Musica(
            slug=slug,
            titulo=titulo,
            artista=artista,
            tom_original=tom_original,
            capotraste=capotraste,
            conteudo=conteudo,
        )
        db.session.add(musica)
        logger.info(f"🎸 Música criada: {slug}")

    db.session.commit()
    return musica


def _slug_proxima_versao(slug_base):
    """
    Retorna o primeiro slug livre no formato "<slug_base>-vN" (N a partir de 2).
    Usado quando o usuário opta por salvar uma nova versão de uma cifra já existente.
    """
    n = 2
    while Musica.query.filter_by(slug=f"{slug_base}-v{n}").first() is not None:
        n += 1
    return f"{slug_base}-v{n}"


# --- ROTAS DO MÓDULO DE CIFRAS ---


@cifras_bp.route('/cifras/teclado.js')
def teclado_js():
    """
    Serve o JS dos diagramas de teclado (acordes calculados, sem imagem externa).

    Mesmo padrão das rotas de arquivo estático de app.py (send_from_directory a
    partir da raiz do projeto), mantido aqui por ser específico deste módulo.
    """
    return send_from_directory(_BASE_DIR, 'cifras_teclado.js', mimetype='application/javascript')


@cifras_bp.route('/cifras')
def index():
    """
    Renderiza a página de busca/listagem de cifras.

    Retorna:
        HTML: Página de cifras (placeholder de busca/lista)
    """
    logger.info("🎸 Acessando página de cifras")
    musicas = Musica.query.order_by(Musica.criado_em.desc()).all()
    return render_template('cifras.html', active_page='cifras', musicas=musicas)


@cifras_bp.route('/cifras/importar', methods=['POST'])
def importar():
    """
    Importa uma cifra do CifraClub (formato "simplificada") a partir de uma URL.

    Dados esperados (formulário):
        url (str): URL completa da página .../simplificada.html no CifraClub
        acao (str, opcional): 'sobrescrever' ou 'nova_versao' quando o slug já existe

    Retorna:
        Redireciona para /cifras/<slug> em caso de sucesso; caso contrário,
        volta para /cifras com uma mensagem de erro (flash).
    """
    url = (request.form.get('url') or '').strip()
    if not url:
        flash('❌ Informe a URL da música no CifraClub.', 'error')
        return redirect(url_for('cifras.index'))

    try:
        from cifras_scraper import (
            buscar_html_cifraclub,
            parsear_cifra_simplificada,
            gerar_slug,
        )
    except ImportError:
        logger.error("Dependência 'beautifulsoup4' ausente - importação de cifras indisponível")
        flash('❌ Importação indisponível: dependência não instalada no servidor.', 'error')
        return redirect(url_for('cifras.index'))

    try:
        html = buscar_html_cifraclub(url)
        dados = parsear_cifra_simplificada(html)
    except Exception as e:
        logger.warning(f"Falha ao importar cifra de {url}: {e}")
        flash(f'❌ Não foi possível importar essa cifra: {e}', 'error')
        return redirect(url_for('cifras.index'))

    slug = gerar_slug(dados['titulo'], dados.get('artista'))
    if not slug:
        flash('❌ Não consegui gerar um identificador para essa música.', 'error')
        return redirect(url_for('cifras.index'))

    acao = (request.form.get('acao') or '').strip()
    existente = Musica.query.filter_by(slug=slug).first()

    # Já existe e o usuário ainda não escolheu o que fazer: pede confirmação
    if existente and not acao:
        logger.info(f"🎸 Cifra '{slug}' já existe - pedindo confirmação")
        return render_template(
            'cifras_confirmar.html',
            active_page='cifras',
            url=url,
            titulo=dados['titulo'],
            artista=dados.get('artista'),
        )

    # 'nova_versao': salva numa linha nova com sufixo -vN, sem tocar na existente
    if acao == 'nova_versao':
        slug = _slug_proxima_versao(slug)

    salvar_musica(
        slug,
        dados['titulo'],
        dados.get('artista'),
        dados.get('tom_original'),
        dados['linhas'],
        capotraste=dados.get('capotraste'),
    )
    logger.info(f"🎸 Cifra importada do CifraClub: {slug}")
    flash(f'✅ Cifra "{dados["titulo"]}" importada com sucesso!', 'success')
    return redirect(url_for('cifras.cifras_musica', slug=slug))


@cifras_bp.route('/cifras/<slug>')
def cifras_musica(slug):
    """
    Renderiza a página de uma música com acordes e letra.

    Args:
        slug (str): Identificador da música

    Retorna:
        HTML: Página da música ou 404 se não encontrada
    """
    musica = _carregar_musica(slug)
    if not musica:
        abort(404)
    return render_template('cifras_musica.html', active_page='cifras', musica=musica)


@cifras_bp.route('/cifras/<slug>/deletar', methods=['POST'])
def deletar_musica(slug):
    """
    Exclui uma música pelo slug e volta para a listagem de cifras.

    Args:
        slug (str): Identificador da música

    Retorna:
        Redireciona para /cifras com mensagem flash (sucesso ou erro).
    """
    musica = Musica.query.filter_by(slug=slug).first()
    if not musica:
        flash('❌ Música não encontrada.', 'error')
        return redirect(url_for('cifras.index'))

    titulo = musica.titulo
    db.session.delete(musica)
    db.session.commit()
    logger.info(f"🎸 Cifra excluída: {slug}")
    flash(f'✅ Cifra "{titulo}" excluída.', 'success')
    return redirect(url_for('cifras.index'))


@cifras_bp.route('/cifras/api/<slug>')
def api_cifras_musica(slug):
    """
    Retorna os dados de uma música em JSON.

    Mesma carga usada pelas páginas HTML, para o front-end de transposição de tom.

    Args:
        slug (str): Identificador da música

    Retorna:
        JSON com os dados da música ou {'error': ...} com status 404
    """
    musica = _carregar_musica(slug)
    if not musica:
        return jsonify({'error': f'Música não encontrada: {slug}'}), 404
    return jsonify(musica)
