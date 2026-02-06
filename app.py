import os
import requests
from flask import Flask, jsonify, send_file, send_from_directory
from flask_cors import CORS
import json
import time
import hashlib
from PIL import Image
from io import BytesIO

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, 'fotos_cache.json')
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, 'thumbnails')
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

# Configuração do GitHub
GITHUB_REPO = "gbrow/fotos-mapa"
GITHUB_BRANCH = "main"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

# Tamanho da thumbnail
THUMBNAIL_SIZE = (300, 300)

def get_github_headers():
    """Headers para requests do GitHub"""
    headers = {
        'User-Agent': 'MapaFotosApp/1.0',
        'Accept': 'application/vnd.github.v3+json'
    }
    if GITHUB_TOKEN:
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
    return headers

def get_github_raw_url(filename):
    """Gera URL raw do GitHub para um arquivo"""
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{filename}"

def get_github_api_url(path=""):
    """Gera URL da API do GitHub"""
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

def listar_arquivos_github():
    """Lista arquivos do repositório GitHub"""
    try:
        print(f"🔍 Conectando ao GitHub: {GITHUB_REPO}")
        
        response = requests.get(
            get_github_api_url(),
            headers=get_github_headers(),
            timeout=30
        )
        
        print(f"📡 Status GitHub: {response.status_code}")
        
        if response.status_code == 200:
            arquivos = response.json()
            print(f"✅ Conectado ao GitHub")
            
            # Retornar lista de nomes de arquivos
            nomes_arquivos = []
            for item in (arquivos if isinstance(arquivos, list) else [arquivos]):
                if isinstance(item, dict):
                    nome = item.get('name', '')
                    tipo = item.get('type', '')
                    if tipo == 'file':
                        nomes_arquivos.append(nome)
            
            print(f"📁 {len(nomes_arquivos)} arquivos encontrados")
            return nomes_arquivos
            
        else:
            print(f"❌ Erro GitHub: {response.status_code}")
            print(f"📝 Resposta: {response.text[:200]}")
            return []
            
    except Exception as e:
        print(f"❌ Erro ao conectar ao GitHub: {e}")
        return []

def criar_thumbnail_da_url(url, filename):
    """Cria thumbnail a partir de uma URL"""
    try:
        # Gerar nome único para thumbnail
        thumb_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        thumb_name = f"{thumb_hash}.jpg"
        thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_name)
        
        # Se já existe, retornar
        if os.path.exists(thumb_path):
            return thumb_name
        
        # Baixar imagem e criar thumbnail
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            img = Image.open(BytesIO(response.content))
            img.thumbnail(THUMBNAIL_SIZE)
            
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            img.save(thumb_path, 'JPEG', quality=80, optimize=True)
            print(f"  ✅ Thumbnail criada: {filename}")
            return thumb_name
            
    except Exception as e:
        print(f"  ⚠️  Erro ao criar thumbnail: {e}")
    
    return None

def processar_arquivos():
    """Processa arquivos do GitHub"""
    print("🔄 Processando arquivos...")
    
    # Listar arquivos
    arquivos = listar_arquivos_github()
    
    if not arquivos:
        print("⚠️  Nenhum arquivo encontrado")
        return {'fotos': [], 'trajetos': []}
    
    fotos = []
    trajetos = []
    
    # Contadores
    total_imagens = 0
    total_kmls = 0
    
    for filename in arquivos:
        url = get_github_raw_url(filename)
        
        # Processar imagens
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            total_imagens += 1
            
            thumb_name = criar_thumbnail_da_url(url, filename)
            
            if thumb_name:
                # Coordenadas de exemplo (centro do Brasil com variação)
                import random
                lat_base = -15.7942
                lon_base = -47.8822
                
                fotos.append({
                    'filename': filename,
                    'original_url': url,
                    'thumbnail': f'/thumbnail/{thumb_name}',
                    'full_image': url,
                    'latitude': lat_base + (random.random() - 0.5) * 5,
                    'longitude': lon_base + (random.random() - 0.5) * 5,
                    'data_tirada': '2024-01-01'
                })
        
        # Processar KMLs (simplificado - apenas marca como existente)
        elif filename.lower().endswith('.kml'):
            total_kmls += 1
            trajetos.append({
                'type': 'LineString',
                'name': f'Trajeto: {filename}',
                'filename': filename,
                'coordinates': [
                    [-15.7942, -47.8822],
                    [-15.8000, -47.8900],
                    [-15.8100, -47.9000]
                ],
                'color': '#FF0000',
                'weight': 3,
                'opacity': 0.7
            })
            print(f"  🗺️  KML encontrado: {filename}")
    
    # Salvar cache
    cache_data = {
        'fotos': fotos,
        'trajetos': trajetos,
        'processed_at': time.time(),
        'total_files': len(arquivos),
        'image_count': total_imagens,
        'kml_count': total_kmls
    }
    
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Processamento concluído:")
    print(f"   📸 Imagens: {len(fotos)}")
    print(f"   🗺️  KMLs: {len(trajetos)}")
    print(f"   📁 Total arquivos: {len(arquivos)}")
    
    return cache_data

# Rotas da API
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

@app.route('/api/fotos')
def listar_fotos():
    """Retorna apenas fotos"""
    try:
        print("📡 Recebida requisição /api/fotos")
        
        # Usar cache se disponível e recente (< 1 hora)
        if os.path.exists(CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            if cache_age < 3600:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"📊 Retornando {len(data.get('fotos', []))} fotos do cache")
                    return jsonify(data.get('fotos', []))
        
        # Processar e retornar
        data = processar_arquivos()
        return jsonify(data.get('fotos', []))
        
    except Exception as e:
        print(f"❌ Erro em /api/fotos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Erro interno', 'message': str(e)}), 500

@app.route('/api/kml')
def listar_kml():
    """Retorna trajetos KML"""
    try:
        if os.path.exists(CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            if cache_age < 3600:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return jsonify({'trajetos': data.get('trajetos', [])})
        
        data = processar_arquivos()
        return jsonify({'trajetos': data.get('trajetos', [])})
        
    except Exception as e:
        print(f"❌ Erro em /api/kml: {e}")
        return jsonify({'trajetos': []})

@app.route('/api/all')
def listar_tudo():
    """Retorna tudo"""
    try:
        if os.path.exists(CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            if cache_age < 3600:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return jsonify(json.load(f))
        
        return jsonify(processar_arquivos())
        
    except Exception as e:
        print(f"❌ Erro em /api/all: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/thumbnail/<nome_arquivo>')
def servir_thumbnail(nome_arquivo):
    """Serve thumbnail"""
    caminho = os.path.join(THUMBNAIL_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    
    # Thumbnail padrão
    img = Image.new('RGB', (300, 200), color='#f0f0f0')
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/jpeg')

@app.route('/api/status')
def status():
    """Status do sistema"""
    try:
        cache_exists = os.path.exists(CACHE_FILE)
        cache_age = 0
        fotos_count = 0
        trajetos_count = 0
        
        if cache_exists:
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    fotos_count = len(data.get('fotos', []))
                    trajetos_count = len(data.get('trajetos', []))
            except:
                pass
        
        return jsonify({
            'status': 'online',
            'github_repo': GITHUB_REPO,
            'cache_exists': cache_exists,
            'cache_age_minutes': int(cache_age / 60),
            'fotos_cached': fotos_count,
            'trajetos_cached': trajetos_count,
            'thumbnails': len(os.listdir(THUMBNAIL_FOLDER)) if os.path.exists(THUMBNAIL_FOLDER) else 0,
            'timestamp': time.time()
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'status': 'error'}), 500

@app.route('/api/refresh')
def refresh():
    """Força atualização"""
    data = processar_arquivos()
    return jsonify({
        'success': True,
        'fotos': len(data.get('fotos', [])),
        'trajetos': len(data.get('trajetos', [])),
        'message': 'Cache atualizado'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🗺️  MAPA DE FOTOS - VERSÃO FINAL")
    print("=" * 60)
    print(f"📁 Repositório: {GITHUB_REPO}")
    print(f"🔑 Token GitHub: {'Sim' if GITHUB_TOKEN else 'Não (público)'}")
    print(f"🌐 Porta: {port}")
    print("=" * 60)
    
    # Cache inicial
    try:
        print("🔄 Criando cache inicial...")
        data = processar_arquivos()
        print(f"✅ Cache criado: {len(data.get('fotos', []))} fotos")
    except Exception as e:
        print(f"⚠️  Erro no cache inicial: {e}")
    
    print(f"\n🚀 Servidor pronto!")
    print(f"📊 Status: http://localhost:{port}/api/status")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)