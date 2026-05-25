"""
routes/leiloes.py - Blueprint para gerenciamento de leilões e garimpos
Integra com o backend de IA para busca de leilões
"""

import logging
import requests
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from extensions import db
from models import get_config
from utils.helpers import get_api_url, build_api_endpoint

logger = logging.getLogger(__name__)

# Criar blueprint
leiloes_bp = Blueprint('leiloes', __name__)

# Variáveis globais que serão injetadas
log_path = None


def setup_leiloes_blueprint(app, log_path_ref):
    """
    Injeta dependências no blueprint de leilões.
    
    Args:
        app (Flask): Aplicação Flask
        log_path_ref (str): Caminho para arquivo de logs
    """
    global log_path
    log_path = log_path_ref


# --- ROTAS DO SISTEMA DE LEILÕES (GARIMPO) ---


@leiloes_bp.route('/leiloes')
def leiloes_index():
    """
    Renderiza a interface de Leilões com configurações.
    
    Retorna:
        HTML: Página de interface de leilões com formulário de configuração
    """
    logger.info("📊 Acessando página de leilões")
    config = get_config()
    return render_template('leiloes.html', 
                          config=config, 
                          active_page='leiloes')


@leiloes_bp.route('/update_auction_config', methods=['POST'])
def update_auction_config():
    """
    Salva as configurações específicas do sistema de Leilões.
    
    Dados esperados (formulário):
        days[]: Lista de dias da semana (0-6, 0=segunda)
        time: Horário no formato HH:MM
        api_url: URL do backend de leilões
    
    Retorna:
        Redireciona para /leiloes com flash message
    """
    try:
        conf = get_config()
        
        # Salva dias (lista) como string separada por vírgula
        days = request.form.getlist('days')
        conf.auction_schedule_days = ",".join(days) if days else ""
        
        # Salva horário
        conf.auction_schedule_time = request.form.get('time', '05:00')
        
        # Salva URL da API de leilões
        conf.auction_api_url = request.form.get('api_url', '').strip()
        
        db.session.commit()
        
        logger.info(f"⚙️ Configurações de leilão salvas: dias={conf.auction_schedule_days}, hora={conf.auction_schedule_time}, url={conf.auction_api_url}")
        flash('✅ Configurações de Leilão salvas!', 'success')
    except Exception as e:
        logger.error(f"❌ Erro ao salvar configurações de leilão: {e}")
        flash(f'❌ Erro ao salvar configurações: {str(e)}', 'error')
    
    return redirect(url_for('leiloes.leiloes_index'))


# --- API PROXIES PARA O BACKEND DE LEILÕES ---


@leiloes_bp.route('/api/history')
def api_history():
    """
    Proxy para histórico de leilões do backend.
    
    Retorna:
        JSON com histórico de leilões processados
    
    Exemplos de resposta:
        Sucesso:
        [
            {
                "id": 1,
                "title": "Domínio exemplo.com",
                "status": "completed",
                "date": "2026-04-18"
            }
        ]
        
        Erro:
        {
            "error": "Erro de conexão com backend: ..."
        }
    """
    try:
        logger.info("📋 Requisição para histórico de leilões")
        
        # Constrói URL do endpoint
        url = build_api_endpoint('/api/auction/history', 'auction')
        
        # Timeout aumentado para 30s para acomodar consultas maiores
        resp = requests.get(url, timeout=30)
        
        logger.debug(f"📊 Histórico recebido: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao obter histórico de leilões")
        return jsonify({'error': 'Timeout ao conectar com backend'}), 504
    except Exception as e:
        logger.error(f"❌ Erro ao conectar com backend de leilões: {e}")
        return jsonify({'error': f'Erro de conexão com backend: {str(e)}'}), 500


@leiloes_bp.route('/api/lotes')
def api_lotes():
    """
    Proxy para listar lotes disponíveis no backend.
    
    Parâmetros de query (opcionais):
        page: Número da página
        limit: Itens por página
        filter: Filtro de busca
    
    Retorna:
        JSON com lista de lotes
    """
    try:
        logger.info(f"📦 Requisição para lotes com parâmetros: {request.args}")
        
        url = build_api_endpoint('/api/lotes', 'auction')
        resp = requests.get(url, params=request.args, timeout=10)
        
        logger.debug(f"📦 Lotes recebidos: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao obter lotes")
        return jsonify({'error': 'Timeout ao conectar com backend'}), 504
    except Exception as e:
        logger.error(f"❌ Erro ao obter lotes: {e}")
        return jsonify({'error': f'Erro de conexão com backend: {str(e)}'}), 500


@leiloes_bp.route('/api/dominios')
def api_dominios():
    """
    Proxy para listar domínios disponíveis.
    
    Retorna:
        JSON com lista de domínios
    """
    try:
        logger.info("🌐 Requisição para lista de domínios")
        
        url = build_api_endpoint('/dominios', 'auction')
        resp = requests.get(url, timeout=10)
        
        logger.debug(f"🌐 Domínios recebidos: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao obter domínios")
        return jsonify([]), 504
    except Exception as e:
        logger.error(f"❌ Erro ao obter domínios: {e}")
        return jsonify([]), 500


@leiloes_bp.route('/api/stats')
def api_stats():
    """
    Proxy para estatísticas de leilões.
    
    Retorna:
        JSON com estatísticas (total, completados, em progresso, etc)
    """
    try:
        logger.info("📈 Requisição para estatísticas de leilões")
        
        url = build_api_endpoint('/stats', 'auction')
        resp = requests.get(url, timeout=10)
        
        logger.debug(f"📈 Stats recebidas: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao obter estatísticas")
        return jsonify({'error': 'Timeout'}), 504
    except Exception as e:
        logger.error(f"❌ Erro ao obter estatísticas: {e}")
        return jsonify({'error': str(e)}), 500


@leiloes_bp.route('/api/auction/item/<int:item_id>', methods=['DELETE'])
def api_delete_item(item_id):
    """
    Proxy para deletar um item específico pelo ID.
    
    Args:
        item_id (int): ID do item a deletar
    
    Retorna:
        JSON com resultado da operação
    """
    try:
        logger.info(f"🗑️ Deletando item {item_id}")
        
        url = build_api_endpoint(f'/api/auction/item/{item_id}', 'auction')
        resp = requests.delete(url, timeout=10)
        
        logger.info(f"✅ Item {item_id} deletado: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error(f"⏱️ Timeout ao deletar item {item_id}")
        return jsonify({'status': 'error', 'message': 'Timeout'}), 504
    except Exception as e:
        logger.error(f"❌ Erro ao deletar item {item_id}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@leiloes_bp.route('/api/lote/delete', methods=['DELETE'])
def api_delete_lote():
    """
    Proxy para deletar um lote completo.
    
    Dados esperados (JSON):
        {
            "lote_id": 123
        }
    
    Retorna:
        JSON com resultado da operação
    """
    try:
        logger.info(f"🗑️ Deletando lote: {request.json}")
        
        url = build_api_endpoint('/lote', 'auction')
        resp = requests.delete(url, json=request.json, timeout=10)
        
        logger.info(f"✅ Lote deletado: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao deletar lote")
        return jsonify({'status': 'error', 'message': 'Timeout'}), 504
    except Exception as e:
        logger.error(f"❌ Erro ao deletar lote: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@leiloes_bp.route('/api/termo/delete', methods=['DELETE'])
def api_delete_termo():
    """
    Proxy para deletar um termo de busca específico.
    
    Dados esperados (JSON):
        {
            "termo": "domínio.com"
        }
    
    IMPORTANTE: termo é obrigatório por segurança (previne deleção acidental de todos)
    
    Retorna:
        JSON com resultado da operação
    """
    try:
        # Segurança: Garante que um termo foi enviado para não acionar exclusão total
        if not request.json or 'termo' not in request.json:
            logger.warning("⚠️ Tentativa de deletar termo sem especificar termo")
            return jsonify({
                'status': 'error', 
                'message': 'Termo obrigatório para esta ação'
            }), 400
        
        termo = request.json.get('termo')
        logger.info(f"🗑️ Deletando termo: {termo}")
        
        url = build_api_endpoint('/api/auction/terms', 'auction')
        resp = requests.delete(url, json=request.json, timeout=10)
        
        logger.info(f"✅ Termo deletado: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao deletar termo")
        return jsonify({'status': 'error', 'message': 'Timeout'}), 504
    except Exception as e:
        logger.error(f"❌ Erro ao deletar termo: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@leiloes_bp.route('/api/lotes/delete-all', methods=['DELETE'])
def api_delete_all_lotes():
    """
    Proxy para deletar TODOS os lotes do histórico.
    
    ⚠️ CUIDADO: Esta operação é irreversível!
    
    Retorna:
        JSON com resultado da operação
    """
    try:
        logger.warning("⚠️ OPERAÇÃO PERIGOSA: Deletando TODOS os lotes")
        
        url = build_api_endpoint('/api/auction/history', 'auction')
        resp = requests.delete(url, timeout=10)
        
        logger.info(f"✅ Todos os lotes deletados: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao deletar todos os lotes")
        return jsonify({'status': 'error', 'message': 'Timeout'}), 504
    except Exception as e:
        logger.error(f"❌ Erro ao deletar todos os lotes: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@leiloes_bp.route('/api/termos/delete-all', methods=['DELETE'])
def api_delete_all_termos():
    """
    Proxy para deletar TODOS os termos de busca.
    
    ⚠️ CUIDADO: Esta operação é irreversível!
    
    Retorna:
        JSON com resultado da operação
    """
    try:
        logger.warning("⚠️ OPERAÇÃO PERIGOSA: Deletando TODOS os termos")
        
        url = build_api_endpoint('/api/auction/terms', 'auction')
        resp = requests.delete(url, timeout=10)
        
        logger.info(f"✅ Todos os termos deletados: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao deletar todos os termos")
        return jsonify({'status': 'error', 'message': 'Timeout'}), 504
    except Exception as e:
        logger.error(f"❌ Erro ao deletar todos os termos: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@leiloes_bp.route('/api/leilao/rastrear', methods=['POST'])
def api_rastrear():
    """
    Proxy para rastrear/buscar leilões com termos específicos.
    
    Dados esperados (JSON):
        {
            "termos": ["domínio", "site"],
            "filtros": {"tipo": "leilão", "status": "ativo"}
        }
    
    Nota: Este endpoint pode levar tempo significativo se houver muitos resultados.
    Timeout aumentado para 210 segundos (3.5 minutos).
    
    Retorna:
        JSON com resultados de busca
    """
    try:
        logger.info(f"🔍 Rastreando leilões: {request.json}")
        
        url = build_api_endpoint('/api/auction/search', 'auction')
        
        # Timeout aumentado para 210s para suportar termos com muitos resultados
        resp = requests.post(url, json=request.json, timeout=210)
        
        logger.info(f"✅ Busca concluída: {resp.status_code}")
        return jsonify(resp.json()), resp.status_code
        
    except requests.Timeout:
        logger.error("⏱️ Timeout ao rastrear leilões (busca demorou mais de 210s)")
        return jsonify({
            'message': 'Timeout: a busca demorou muito tempo. Tente termos mais específicos.'
        }), 504
    except Exception as e:
        logger.error(f"❌ Erro ao rastrear leilões: {e}")
        return jsonify({
            'message': f'Erro ao comunicar com backend: {str(e)}'
        }), 500
