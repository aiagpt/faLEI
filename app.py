import os
import threading
import zipfile
import io
from flask import Flask, render_template, request, jsonify, send_file
from services.gemini_service import GeminiService
from services.tts_service import TTSService
from utils.web_scraper import buscar_lei_por_url
from config.settings import settings
from database.job_db import JobDatabase

app = Flask(__name__)
db = JobDatabase()

# Modo de teste: pula o TTS e só testa o Gemini
SKIP_TTS = os.getenv('SKIP_TTS', '0') == '1'

if SKIP_TTS:
    print("[MODO TESTE] SKIP_TTS ativado — TTS será ignorado.")

# Job atual em processamento
current_job_id = None

def processar_lei(job_id: int, url: str):
    """Processa a lei em background com checkpoints."""
    global current_job_id
    current_job_id = job_id
    
    try:
        job = db.get_job(job_id)
        
        # Verificar se há checkpoint para retomar
        texto_original = job.get('checkpoint_text')
        texto_humanizado = job.get('checkpoint_humanized')
        checkpoint_stage = job.get('checkpoint_stage')
        
        # 1. Buscar lei (ou usar checkpoint)
        if not texto_original:
            db.update_job(job_id, status='fetching', progress=10, message='Buscando lei...', checkpoint_stage='fetching')
            try:
                texto_original = buscar_lei_por_url(url)
                if not texto_original:
                     raise Exception("Conteúdo da lei não encontrado (procure por 'Art.' ou 'Artigo').")
            except Exception as e:
                db.update_job(job_id, status='error', message=str(e), error=str(e))
                current_job_id = None
                return
            
            db.update_job(job_id, checkpoint_text=texto_original, checkpoint_stage='fetched')
        else:
            print(f"[Job {job_id}] Retomando da etapa: {checkpoint_stage}")
        
        # 2. Humanizar (ou usar checkpoint)
        if not texto_humanizado:
            db.update_job(job_id, status='humanizing', progress=30, message='Humanizando texto com Gemini...', checkpoint_stage='humanizing')
            gemini = GeminiService()
            texto_humanizado = gemini.humanizar_texto(texto_original)
            
            if not texto_humanizado:
                db.update_job(job_id, status='error', message='Erro na humanização', error='Gemini falhou')
                current_job_id = None
                return
            
            db.update_job(job_id, checkpoint_humanized=texto_humanizado, checkpoint_stage='humanized')

        # ── MODO TESTE: pular TTS ──────────────────────────────
        if SKIP_TTS:
            db.update_job(job_id,
                          status='complete',
                          progress=100,
                          message='Concluído! (modo teste — sem áudio)',
                          filename=None,
                          checkpoint_stage='complete')
            current_job_id = None
            return
        # ──────────────────────────────────────────────────────

        # Helper para atualizar progresso
        def update_progress(percent, msg):
            db.update_job(job_id, status='generating', progress=percent, message=msg, checkpoint_stage='generating')

        # 3. Gerar áudio
        db.update_job(job_id, status='generating', progress=40, message='Iniciando geração de áudio...', checkpoint_stage='generating')
        tts = TTSService(voice_name="pt-BR-Wavenet-B")
        
        job_dir = os.path.join("jobs", str(job_id))
        os.makedirs(job_dir, exist_ok=True)
        
        base_name = os.path.basename(url).replace('.html', '').replace('.htm', '')
        if not base_name: 
            base_name = f"job_{job_id}"
            
        nome_arquivo = os.path.join(job_dir, f"{base_name}.mp3")
        
        if tts.sintetizar_arquivo(texto_humanizado, nome_arquivo, progress_callback=update_progress):
            # 4. Gerar timestamps
            db.update_job(job_id, status='analyzing', progress=90, message='Gerando sincronização por frases...', checkpoint_stage='analyzing')
            
            try:
                from utils.sentence_sync import generate_sentence_timestamps, save_timestamps
                timestamps = generate_sentence_timestamps(nome_arquivo, texto_humanizado)
                timestamp_file = nome_arquivo.replace('.mp3', '_timestamps.json')
                save_timestamps(timestamps, timestamp_file)
                print(f"[OK] Sincronizacao por frases configurada!")
            except Exception as e:
                print(f"[!] Erro ao gerar timestamps: {e}")
            
            db.update_job(job_id, status='complete', progress=100, message='Concluído!', filename=nome_arquivo, checkpoint_stage='complete')
        else:
            db.update_job(job_id, status='error', message='Erro ao gerar áudio', error='TTS falhou')
            
    except Exception as e:
        db.update_job(job_id, status='error', message=f'Erro: {str(e)}', error=str(e))
    finally:
        current_job_id = None


@app.route('/')
def index():
    """Página principal."""
    return render_template('index.html')

@app.route('/history')
def history():
    """Página de histórico."""
    return render_template('history.html')


@app.route('/job-text/<int:job_id>')
def job_text(job_id):
    """Retorna o texto humanizado de um job."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job não encontrado'}), 404
    
    # Retornar texto humanizado ou original
    text = job.get('checkpoint_humanized') or job.get('checkpoint_text') or ''
    
    return jsonify({'text': text})

@app.route('/job-timestamps/<int:job_id>')
def job_timestamps(job_id):
    """Retorna os timestamps de um job."""
    job = db.get_job(job_id)
    if not job or not job.get('filename'):
        return jsonify({'error': 'Job não encontrado'}), 404
    
    timestamp_file = job['filename'].replace('.mp3', '_timestamps.json')
    
    if os.path.exists(timestamp_file):
        import json
        with open(timestamp_file, 'r', encoding='utf-8') as f:
            timestamps = json.load(f)
        return jsonify({'timestamps': timestamps})
    else:
        return jsonify({'timestamps': []})

@app.route('/process', methods=['POST'])
def process():
    """Inicia o processamento de uma lei."""
    data = request.json
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL é obrigatória'}), 400
    
    # Validar configurações
    errors = settings.validate()
    if errors:
        return jsonify({'error': f'Configuração inválida: {", ".join(errors)}'}), 400
    
    # Criar job no banco
    job_id = db.create_job(url)
    
    # Processar em background
    thread = threading.Thread(target=processar_lei, args=(job_id, url))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'job_id': job_id})

@app.route('/status/<int:job_id>')
def status(job_id):
    """Retorna o status de um job específico."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job não encontrado'}), 404
    
    return jsonify({
        'id': job['id'],
        'url': job['url'],
        'status': job['status'],
        'progress': job['progress'],
        'message': job['message'],
        'filename': job['filename'],
        'created_at': job['created_at'],
        'completed_at': job['completed_at'],
        'error': job['error']
    })

from utils.usage_tracker import usage_tracker

@app.route('/jobs')
def jobs():
    """Retorna todos os jobs."""
    all_jobs = db.get_all_jobs()
    return jsonify(all_jobs)

@app.route('/usage')
def usage_stats():
    """Retorna estatísticas de uso da cota."""
    return jsonify(usage_tracker.get_stats())

@app.route('/download_zip/<int:job_id>')
def download_zip(job_id):
    """Gera e baixa um ZIP com o áudio e o texto."""
    job = db.get_job(job_id)
    if not job or not job['filename']:
        return jsonify({'error': 'Job ou arquivo não encontrado'}), 404
        
    audio_path = job['filename']
    if not os.path.exists(audio_path):
        return jsonify({'error': 'Arquivo de áudio não encontrado no servidor'}), 404
        
    # Texto para incluir
    texto = job.get('checkpoint_humanized') or job.get('checkpoint_text') or "Texto não disponível."
    
    # Criar ZIP em memória
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Adicionar áudio
        arcname_audio = os.path.basename(audio_path)
        zf.write(audio_path, arcname_audio)
        
        # Adicionar texto
        text_filename = os.path.splitext(arcname_audio)[0] + ".txt"
        zf.writestr(text_filename, texto)
        
    memory_file.seek(0)
    
    zip_filename = os.path.splitext(os.path.basename(audio_path))[0] + ".zip"
    
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=zip_filename
    )

@app.route('/delete/<int:job_id>', methods=['DELETE'])
def delete(job_id):
    """Deleta um job."""
    job = db.get_job(job_id)
    if job and job['filename']:
        # Deletar diretório do job
        try:
            # Tentar extrair diretório do arquivo (jobs/ID/)
            file_path = job['filename']
            if os.path.sep in file_path:
                job_dir = os.path.dirname(file_path)
                import shutil
                if os.path.exists(job_dir) and "jobs" in job_dir:
                    shutil.rmtree(job_dir)
            
            # Fallback para deletar apenas arquivo se estiver na raiz (jobs antigos)
            elif os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            print(f"Erro ao deletar arquivos: {e}")
            
    db.delete_job(job_id)
    return jsonify({'success': True})

@app.route('/jobs/clear', methods=['DELETE'])
def clear_all_jobs():
    """Deleta TODOS os jobs."""
    try:
        # 1. Obter todos os jobs para limpar arquivos
        jobs = db.get_all_jobs()
        for job in jobs:
            if job['filename']:
                try:
                    file_path = job['filename']
                    # Se tiver diretório próprio (jobs/ID/)
                    if os.path.sep in file_path:
                        job_dir = os.path.dirname(file_path)
                        import shutil
                        if os.path.exists(job_dir) and "jobs" in job_dir:
                            shutil.rmtree(job_dir)
                    # Fallback
                    elif os.path.exists(file_path):
                        os.remove(file_path)
                except:
                    pass
        
        # 2. Limpar banco
        # Nota: Idealmente adicionar um método clear_all no JobDatabase, mas aqui vamos iterar ou acessar direto
        # Como db.delete_job deleta um por um, vamos fazer um loop por enquanto para garantir consistencia
        # Ou melhor, vamos adicionar um método SQL direto se possível no db, mas não temos acesso fácil ao arquivo do DB agora.
        # Vamos usar o loop que é seguro.
        for job in jobs:
             db.delete_job(job['id'])
             
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/resume/<int:job_id>', methods=['POST'])
def resume_job(job_id):
    """Retoma um job existente sem perder checkpoints."""
    job = db.get_job(job_id)
    if not job:
        return jsonify({'error': 'Job não encontrado'}), 404
    
    # Limpar erro anterior e reiniciar status
    db.update_job(job_id, status='pending', error=None, message='Retomando...')
    
    # Reiniciar processamento em background
    thread = threading.Thread(target=processar_lei, args=(job_id, job['url']))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True})

def resume_pending_jobs():
    """Retoma jobs pendentes ao iniciar o servidor."""
    pending = db.get_pending_jobs()
    
    if pending:
        print(f"\n[INFO] Encontrados {len(pending)} job(s) pendente(s). Retomando...")
        
        for job in pending:
            print(f"   -> Retomando Job #{job['id']}: {job['url']}")
            thread = threading.Thread(target=processar_lei, args=(job['id'], job['url']))
            thread.daemon = True
            thread.start()

if __name__ == '__main__':
    print("=" * 60)
    print("SISTEMA faLei - WEB")
    print("=" * 60)
    print("\n[INFO] Acesse: http://localhost:5000")
    print("[INFO] Historico: http://localhost:5000/history")
    
    # Migrar banco de dados se necessário
    import sqlite3
    conn = sqlite3.connect('jobs.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(jobs)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'checkpoint_stage' not in columns:
        print("\n[INFO] Atualizando banco de dados...")
        cursor.execute("ALTER TABLE jobs ADD COLUMN checkpoint_text TEXT")
        cursor.execute("ALTER TABLE jobs ADD COLUMN checkpoint_humanized TEXT")
        cursor.execute("ALTER TABLE jobs ADD COLUMN checkpoint_stage TEXT")
        conn.commit()
        print("[OK] Banco atualizado!")
    
    conn.close()
    
    # Retomar jobs pendentes
    resume_pending_jobs()
    
    print("\nPressione Ctrl+C para parar o servidor\n")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
