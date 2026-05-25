"""
routes/resumo.py - Blueprint para gerenciamento de resumos de vídeo
Integra com a fila de processamento (SummaryQueue) e API de IA
"""

import logging
import requests
import json
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash
from extensions import db, scheduler
from models import Channel, VideoArchive, SummaryQueue, get_config
from utils.helpers import get_api_url, build_api_endpoint

logger = logging.getLogger(__name__)

# Criar blueprint
resumo_bp = Blueprint('resumo', __name__)

# Variáveis globais que serão injetadas
log_path = None
processar_fila_resumos = None


def setup_resumo_blueprint(app, log_path_ref, process_queue_func):
    """
    Injeta dependências no blueprint de resumos.
    
    Args:
        app (Flask): Aplicação Flask
        log_path_ref (str): Caminho para arquivo de logs
        process_queue_func (callable): Função para processar fila de resumos
    """
    global log_path, processar_fila_resumos
    log_path = log_path_ref
    processar_fila_resumos = process_queue_func


# --- ROTAS DO SISTEMA DE RESUMO DE VÍDEO ---


@resumo_bp.route('/resumo')
def resumo_index():
    """
    Renderiza a interface de resumo de vídeo
    
    Retorna:
        HTML: Página de interface de resumo com formulário para adicionar vídeos à fila
    """
    logger.info("📋 Acessando página de resumo")
    
    # Obtém status da fila para exibição
    fila_status = {
        'pending': SummaryQueue.query.filter_by(status='pending').count(),
        'completed': SummaryQueue.query.filter_by(status='completed').count(),
        'failed': SummaryQueue.query.filter_by(status='failed').count(),
        'paused': SummaryQueue.query.filter_by(status='paused').count()
    }
    
    return render_template('resumo.html', 
                          active_page='resumo',
                          fila_status=fila_status)


@resumo_bp.route('/resumo', methods=['POST'])
def api_resumo():
    """
    Gera resumo de um vídeo do YouTube.
    
    Comunica com o backend de IA para processar a URL do vídeo.
    
    Dados esperados (JSON):
        {
            "video_url": "https://www.youtube.com/watch?v=xxxxx",
            "force": false  # Opcional: forçar reprocessamento
        }
    
    Retorna:
        JSON com resultado do resumo ou erro
    
    Exemplos de resposta:
        Sucesso:
        {
            "status": "success",
            "summary": "Resumo do vídeo...",
            "title": "Título do vídeo",
            "video_id": "xxxxx"
        }
        
        Erro:
        {
            "status": "error",
            "message": "Descrição do erro"
        }
    """
    try:
        data = request.get_json()
        video_url = data.get('video_url', '').strip()
        
        if not video_url:
            return jsonify({'status': 'error', 'message': 'URL do vídeo obrigatória'}), 400
        
        logger.info(f"📺 Gerando resumo para: {video_url}")
        
        # Proxy para o backend de IA (Atualizado para a nova rota)
        api_url = build_api_endpoint('/summarize-video', 'youtube')
        
        try:
            response = requests.post(
                api_url,
                json={'video_url': video_url},
                timeout=300  # Resumos podem levar tempo
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Tenta arquivar o resultado
                try:
                    summary_text = result.get('summary', result.get('resumo', result.get('texto', '')))
                    if result.get('status') == 'success' or bool(summary_text):
                        # Extrai dados do vídeo
                        video_id = result.get('video_id')
                        title = result.get('title', 'Sem título')
                        
                        # Fallback se a IA não retornar o ID
                        if not video_id:
                            if 'v=' in video_url: video_id = video_url.split('v=')[1].split('&')[0]
                            elif 'youtu.be/' in video_url: video_id = video_url.split('youtu.be/')[1].split('?')[0]
                            elif '/shorts/' in video_url: video_id = video_url.split('/shorts/')[1].split('?')[0]
                        
                        # Verifica se já existe para não duplicar
                        existing = VideoArchive.query.filter_by(video_id=video_id).first() if video_id else None
                        if not existing and video_id and summary_text:
                            # Detecta qual canal o vídeo pertence
                            channel_id = result.get('channel_id', '')
                            channel_name = result.get('channel_name', 'Desconhecido')
                            published_at = result.get('published_at') or result.get('publication_date') or 'Desconhecida'
                            
                            archive = VideoArchive(
                                channel_id=channel_id,
                                channel_name=channel_name,
                                video_id=video_id,
                                title=title,
                                published_at=published_at,
                                summary=summary_text,
                                full_transcript=result.get('transcript'),
                                extracted_tags=result.get('tags'),
                                provider=result.get('provider'),
                                tokens_used=result.get('tokens_used')
                            )
                            db.session.add(archive)
                            db.session.commit()
                            logger.info(f"✅ Vídeo arquivado no Cofre: {title}")
                
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao arquivar resultado: {e}")
                
                return jsonify(result), response.status_code
            else:
                error_msg = response.text or "Erro desconhecido"
                logger.error(f"❌ Erro da API: {response.status_code} - {error_msg}")
                return jsonify({
                    'status': 'error',
                    'message': f'Erro da API (HTTP {response.status_code})'
                }), response.status_code
                
        except requests.Timeout:
            logger.error("⏱️ Timeout ao chamar API de resumo")
            return jsonify({
                'status': 'error',
                'message': 'Timeout: o resumo demorou muito tempo'
            }), 504
        except Exception as e:
            logger.error(f"❌ Erro ao comunicar com API: {e}")
            return jsonify({
                'status': 'error',
                'message': f'Erro de conexão: {str(e)}'
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro em /api/resumo: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@resumo_bp.route('/archive-summary', methods=['POST'])
def api_archive_summary():
    """
    Arquiva um resumo no Cofre de Conhecimento.
    
    Dados esperados (JSON):
        {
            "video_id": "xxxxx",
            "title": "Título",
            "summary": "Resumo do vídeo",
            "channel_id": "UCxxxxx",
            "channel_name": "Nome do Canal"
        }
    
    Retorna:
        JSON com status da operação
    """
    try:
        data = request.get_json()
        video_id = data.get('video_id', '').strip()
        
        if not video_id:
            return jsonify({
                'status': 'error',
                'message': 'video_id obrigatório'
            }), 400
        
        # Verifica se já existe
        existing = VideoArchive.query.filter_by(video_id=video_id).first()
        if existing:
            return jsonify({
                'status': 'warning',
                'message': 'Este vídeo já está no Cofre'
            }), 200
        
        # Cria novo registro
        archive = VideoArchive(
            video_id=video_id,
            title=data.get('title', 'Sem título'),
            summary=data.get('summary', ''),
            channel_id=data.get('channel_id', ''),
            channel_name=data.get('channel_name', ''),
            full_transcript=data.get('full_transcript'),
            extracted_tags=data.get('extracted_tags'),
            provider=data.get('provider'),
            tokens_used=data.get('tokens_used')
        )
        
        db.session.add(archive)
        db.session.commit()
        
        logger.info(f"✅ Resumo arquivado: {archive.title}")
        
        return jsonify({
            'status': 'success',
            'message': 'Resumo arquivado com sucesso',
            'video_id': video_id
        }), 201
        
    except Exception as e:
        logger.error(f"❌ Erro em /api/archive-summary: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@resumo_bp.route('/api/summarize-text', methods=['POST'])
def api_summarize_text():
    """
    Sumariza um texto arbitrário usando o backend de IA.
    
    Dados esperados (JSON):
        {
            "text": "Texto para sumarizar...",
            "language": "pt"  # Opcional
        }
    
    Retorna:
        JSON com texto sumarizado
    """
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        text = data.get('text', '').strip()
        
        if not text:
            return jsonify({
                'status': 'error',
                'message': 'Texto obrigatório'
            }), 400
        
        logger.info(f"📝 Sumarizando texto ({len(text)} caracteres)")
        
        # Remove quebras de linha que podem causar erro 422 no Pydantic do backend
        text_clean = text.replace('\n', ' ').replace('\r', ' ')
        
        # Proxy para o backend
        api_url = build_api_endpoint('/api/summarize-text', 'youtube')
        
        try:
            response = requests.post(
                api_url,
                json={'title': title, 'text': text_clean},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Tenta arquivar o resultado
                try:
                    summary_text = result.get('summary', result.get('resumo', result.get('texto', '')))
                    if result.get('status') == 'success' or bool(summary_text):
                        # Gera um ID único para o texto (baseado em UUID)
                        text_id = f"text_{uuid.uuid4().hex[:12]}"
                        
                        # Verifica se já existe (por título)
                        existing = VideoArchive.query.filter_by(title=title).filter_by(channel_name='Manual').first() if title else None
                        
                        if not existing and summary_text:
                            # Data de publicação é a data atual no formato ISO
                            published_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            
                            archive = VideoArchive(
                                video_id=text_id,
                                title=title or 'Resumo Manual',
                                published_at=published_at,
                                summary=summary_text,
                                channel_id='',
                                channel_name='Manual Input',
                                full_transcript=None,
                                extracted_tags=result.get('tags'),
                                provider=result.get('provider'),
                                tokens_used=result.get('tokens_used')
                            )
                            db.session.add(archive)
                            db.session.commit()
                            logger.info(f"✅ Texto manual arquivado no Cofre: {title}")
                
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao arquivar resultado: {e}")
                
                return jsonify(result), response.status_code
            else:
                logger.error(f"❌ Erro da API: {response.status_code}")
                return jsonify({
                    'status': 'error',
                    'message': f'Erro HTTP {response.status_code}'
                }), response.status_code
                
        except requests.Timeout:
            logger.error("⏱️ Timeout em sumarização de texto")
            return jsonify({
                'status': 'error',
                'message': 'Timeout ao processar texto'
            }), 504
        except Exception as e:
            logger.error(f"❌ Erro ao comunicar: {e}")
            return jsonify({
                'status': 'error',
                'message': str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"❌ Erro em /api/summarize-text: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@resumo_bp.route('/add_to_queue_web', methods=['POST'])
def add_to_queue_web():
    """
    Adiciona um vídeo à fila de resumos via interface web.
    
    Aceita dados via:
    - Formulário tradicional: video_url (form data)
    - AJAX JSON: {"video_url": "..."}
    
    Retorna:
        Redireciona com flash message ou JSON (se AJAX)
    """
    try:
        # Suporta tanto form data quanto JSON
        if request.is_json:
            video_url = request.get_json().get('video_url', '').strip()
        else:
            video_url = request.form.get('video_url', '').strip()
        
        logger.debug(f"📌 DEBUG: video_url recebida: {video_url[:50] if video_url else 'vazia'}")
        
        if not video_url:
            msg = 'URL do vídeo obrigatória'
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'error', 'message': msg}), 400
            else:
                flash(f'⚠️ {msg}', 'warning')
                return redirect(url_for('resumo.resumo_index'))
        
        logger.info(f"📹 Adicionando à fila: {video_url}")
        
        # Verifica duplicatas
        existing = SummaryQueue.query.filter_by(video_url=video_url).first()
        if existing:
            msg = 'Este vídeo já está na fila de processamento'
            logger.warning(f"⚠️ {msg}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'status': 'warning', 'message': msg}), 200
            else:
                flash(f'⚠️ {msg}', 'warning')
                return redirect(url_for('resumo.resumo_index'))
        
        # Adiciona à fila
        queue_item = SummaryQueue(video_url=video_url, status='pending')
        db.session.add(queue_item)
        db.session.commit()
        
        logger.info(f"✅ Vídeo adicionado à fila: {queue_item.id}")
        
        # NÃO processa imediatamente aqui para evitar travamento
        # O scheduler fará isso a cada 5 minutos
        
        msg = 'Vídeo adicionado à fila de resumos'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            logger.debug(f"📌 DEBUG: Retornando JSON com sucesso")
            return jsonify({
                'status': 'success',
                'message': msg,
                'queue_item_id': queue_item.id
            }), 201
        else:
            flash(f'✅ {msg}', 'success')
            return redirect(url_for('resumo.resumo_index'))
        
    except Exception as e:
        logger.error(f"❌ Erro em add_to_queue_web: {e}", exc_info=True)
        msg = str(e)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'status': 'error', 'message': f'Erro no servidor: {msg}'}), 500
        else:
            flash(f'❌ Erro: {msg}', 'error')
            return redirect(url_for('resumo.resumo_index'))


@resumo_bp.route('/fila/status')
def api_fila_status():
    """
    Retorna o status atual da fila de resumos.
    
    Retorna:
        JSON com contagem de itens por status
        
    Exemplo de resposta:
        {
            "pending": 5,
            "processing": 1,
            "completed": 23,
            "failed": 2,
            "paused": 0,
            "total": 31
        }
    """
    try:
        statuses = {
            'pending': SummaryQueue.query.filter_by(status='pending').count(),
            'processing': SummaryQueue.query.filter_by(status='processing').count(),
            'completed': SummaryQueue.query.filter_by(status='completed').count(),
            'failed': SummaryQueue.query.filter_by(status='failed').count(),
            'paused': SummaryQueue.query.filter_by(status='paused').count()
        }
        
        statuses['total'] = sum(statuses.values())
        
        # Loga os totais (restaurando o log antigo)
        log_status = {k: v for k, v in statuses.items() if k in ['pending', 'processing', 'completed', 'failed', 'paused', 'total']}
        logger.debug(f"📊 Status da fila: {log_status}")
        
        # Adiciona a lista detalhada esperada pelo Frontend
        active_items = SummaryQueue.query.filter(
            SummaryQueue.status.in_(['pending', 'processing', 'paused'])
        ).order_by(SummaryQueue.created_at).all()
        
        lista = []
        for i, item in enumerate(active_items):
            lista.append({
                'id': item.id,
                'video_url': item.video_url,
                'status': item.status,
                'posicao': i + 1
            })
            
        statuses['lista'] = lista
        statuses['pendentes'] = len(active_items)
        
        return jsonify(statuses), 200
        
    except Exception as e:
        logger.error(f"❌ Erro em /api/fila/status: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@resumo_bp.route('/fila/action', methods=['POST'])
def api_fila_action():
    """
    Executa ações na fila de resumos (pausar, retomar, remover, etc).
    
    Dados esperados (JSON):
        {
            "action": "pause|resume|remove|process",
            "queue_item_id": 123,  # Opcional: se action é específica de item
            "status": "paused"     # Novo status para filtro de operação em lote
        }
    
    Ações disponíveis:
        - pause: Pausa um item específico
        - resume: Retoma um item específico
        - remove: Remove um item da fila
        - process: Processa imediatamente um item
        - clear: Limpa todos os itens com status específico
    
    Retorna:
        JSON com resultado da ação
    """
    try:
        data = request.get_json()
        action = data.get('action', '').lower()
        queue_item_id = data.get('queue_item_id')
        
        if not action:
            return jsonify({
                'status': 'error',
                'message': 'Ação obrigatória'
            }), 400
        
        logger.info(f"🎯 Ação na fila: {action}")
        
        if action == 'pause':
            # Pausa um item específico
            if not queue_item_id:
                return jsonify({
                    'status': 'error',
                    'message': 'queue_item_id obrigatório para pause'
                }), 400
            
            item = SummaryQueue.query.get(queue_item_id)
            if not item:
                return jsonify({
                    'status': 'error',
                    'message': 'Item não encontrado'
                }), 404
            
            item.status = 'paused'
            db.session.commit()
            logger.info(f"⏸️ Item {queue_item_id} pausado")
            
            return jsonify({
                'status': 'success',
                'message': f'Item pausado',
                'item_id': queue_item_id
            }), 200
        
        elif action == 'resume':
            # Retoma um item pausado
            if not queue_item_id:
                return jsonify({
                    'status': 'error',
                    'message': 'queue_item_id obrigatório para resume'
                }), 400
            
            item = SummaryQueue.query.get(queue_item_id)
            if not item:
                return jsonify({
                    'status': 'error',
                    'message': 'Item não encontrado'
                }), 404
            
            item.status = 'pending'
            db.session.commit()
            logger.info(f"▶️ Item {queue_item_id} retomado")
            
            return jsonify({
                'status': 'success',
                'message': 'Item retomado',
                'item_id': queue_item_id
            }), 200
        
        elif action == 'remove':
            # Remove um item da fila
            if not queue_item_id:
                return jsonify({
                    'status': 'error',
                    'message': 'queue_item_id obrigatório para remove'
                }), 400
            
            item = SummaryQueue.query.get(queue_item_id)
            if not item:
                return jsonify({
                    'status': 'error',
                    'message': 'Item não encontrado'
                }), 404
            
            db.session.delete(item)
            db.session.commit()
            logger.info(f"🗑️ Item {queue_item_id} removido")
            
            return jsonify({
                'status': 'success',
                'message': 'Item removido da fila',
                'item_id': queue_item_id
            }), 200
        
        elif action == 'process':
            # Processa imediatamente um item
            if processar_fila_resumos:
                try:
                    processar_fila_resumos()
                    logger.info("⏱️ Fila processada manualmente")
                    return jsonify({
                        'status': 'success',
                        'message': 'Processamento iniciado'
                    }), 200
                except Exception as e:
                    logger.error(f"❌ Erro ao processar: {e}")
                    return jsonify({
                        'status': 'error',
                        'message': str(e)
                    }), 500
            else:
                return jsonify({
                    'status': 'warning',
                    'message': 'Processador não disponível'
                }), 503
        
        elif action == 'clear':
            # Limpa fila de um status específico
            target_status = data.get('status', 'failed')
            count = SummaryQueue.query.filter_by(status=target_status).delete()
            db.session.commit()
            logger.info(f"🗑️ Limpas {count} entradas com status '{target_status}'")
            
            return jsonify({
                'status': 'success',
                'message': f'Removidos {count} itens',
                'removed_count': count
            }), 200
        
        else:
            return jsonify({
                'status': 'error',
                'message': f'Ação desconhecida: {action}'
            }), 400
        
    except Exception as e:
        logger.error(f"❌ Erro em /api/fila/action: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@resumo_bp.route('/cofre')
def cofre_index():
    """
    Renderiza a interface do Cofre de Conhecimento (Vídeos Arquivados).
    """
    search_query = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    base_query = VideoArchive.query
    
    if search_query:
        search_term = f"%{search_query}%"
        # Filtra procurando a palavra-chave no resumo ou título
        base_query = base_query.filter(
            (VideoArchive.title.ilike(search_term)) | 
            (VideoArchive.summary.ilike(search_term))
        )
        
    base_query = base_query.order_by(VideoArchive.archived_at.desc())
    
    total_records = base_query.count()
    total_pages = (total_records + per_page - 1) // per_page
    
    if page < 1: page = 1
    if page > total_pages and total_pages > 0: page = total_pages
    
    offset = (page - 1) * per_page
    videos = base_query.limit(per_page).offset(offset).all()
        
    return render_template('cofre.html', 
                          videos=videos, 
                          search_query=search_query, 
                          active_page='cofre', 
                          page=page, 
                          total_pages=total_pages, 
                          total_records=total_records)

@resumo_bp.route('/fila/process-now', methods=['POST'])
def fila_process_now():
    """
    Rota de DEBUG: Processa manualmente a fila de resumos.
    Útil para testar sem esperar o scheduler.
    """
    try:
        if not processar_fila_resumos:
            return jsonify({
                'status': 'error',
                'message': 'Processador de fila não disponível'
            }), 503
        
        logger.info("🔴 [MANUAL DEBUG] Iniciando processamento manual da fila...")
        processar_fila_resumos()
        logger.info("🟢 [MANUAL DEBUG] Processamento manual concluído")
        
        return jsonify({
            'status': 'success',
            'message': 'Fila processada manualmente'
        }), 200
        
    except Exception as e:
        logger.error(f"❌ [MANUAL DEBUG] Erro ao processar fila: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@resumo_bp.route('/delete_cofre/<video_id>', methods=['POST'])
def delete_cofre(video_id):
    """Deleta um resumo arquivado no Cofre"""
    archive = VideoArchive.query.filter_by(video_id=video_id).first()
    if archive:
        try:
            db.session.delete(archive)
            db.session.commit()
            flash('Resumo removido do cofre com sucesso.', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao remover: {e}', 'error')
    else:
        flash('Registro não encontrado.', 'error')
        
    return redirect(url_for('resumo.cofre_index'))