import os
import requests
from flask import Flask, jsonify, send_file, send_from_directory
from flask_cors import CORS
import json
import time
import hashlib
from datetime import datetime, timedelta
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
# Token opcional para maior limite (crie em: GitHub > Settings > Developer settings > Personal access tokens)
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

# Tamanho da thumbnail
THUMBNAIL_SIZE = (300, 300)

# Cache de lista de arquivos (24 horas)
LISTA_ARQUIVOS_CACHE_FILE = os.path.join(BASE_DIR, 'github_files_cache.json')
LISTA_ARQUIVOS_CACHE_DURATION = 24 * 3600  # 24 horas

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

def listar_arquivos_github_com_cache():
    """Lista arquivos do GitHub com cache de 24h"""
    try:
        # Verificar cache primeiro
        if os.path.exists(LISTA_ARQUIVOS_CACHE_FILE):
            with open(LISTA_ARQUIVOS_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
                
            cache_time = cache_data.get('cached_at', 0)
            if time.time() - cache_time < LISTA_ARQUIVOS_CACHE_DURATION:
                print(f"📁 Usando cache de arquivos do GitHub ({len(cache_data.get('files', []))} arquivos)")
                return cache_data.get('files', [])
    except:
        pass
    
    # Buscar do GitHub
    print(f"🔍 Buscando arquivos no GitHub: {GITHUB_REPO}")
    
    try:
        response = requests.get(
            get_github_api_url(),
            headers=get_github_headers(),
            timeout=30
        )
        
        if response.status_code == 200:
            arquivos = response.json()
            
            # Filtrar apenas arquivos (não pastas)
            arquivos_filtrados = []
            for arquivo in (arquivos if isinstance(arquivos, list) else [arquivos]):
                if isinstance(arquivo, dict) and arquivo.get('type') == 'file':
                    arquivos_filtrados.append({
                        'name': arquivo.get('name', ''),
                        'size': arquivo.get('size', 0),
                        'type': arquivo.get('type', '')
                    })
            
            print(f"✅ {len(arquivos_filtrados)} arquivos encontrados")
            
            # Salvar cache
            cache_data = {
                'cached_at': time.time(),
                'files': arquivos_filtrados
            }
            with open(LISTA_ARQUIVOS_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)
            
            return arquivos_filtrados
            
        elif response.status_code == 403:  # Rate limit
            print("⚠️  Rate limit do GitHub atingido. Usando cache...")
            # Tentar usar cache antigo se disponível
            if os.path.exists(LISTA_ARQUIVOS_CACHE_FILE):
                with open(LISTA_ARQUIVOS_CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                return cache_data.get('files', [])
            else:
                print("❌ Sem cache disponível")
                return []
        else:
            print(f"❌ Erro GitHub API: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"❌ Erro ao buscar arquivos: {e}")
        return []

def processar_imagem_rapida(url, filename):
    """Processa imagem de forma otimizada (sem EXIF para ser mais rápido)"""
    try:
        print(f"📥 Processando: {filename}")
        
        # Gerar hash para thumbnail
        thumb_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        thumb_filename = f"{thumb_hash}.jpg"
        thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_filename)
        
        # Se thumbnail já existe, usar
        if os.path.exists(thumb_path):
            print(f"  ✅ Thumbnail já existe")
        else:
            # Baixar e criar thumbnail
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                img = Image.open(BytesIO(response.content))
                img.thumbnail(THUMBNAIL_SIZE)
                
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                img.save(thumb_path, 'JPEG', quality=80, optimize=True)
                print(f"  ✅ Thumbnail criada")
            else:
                print(f"  ❌ Erro ao baixar imagem")
                return None
        
        # Usar coordenadas fixas para teste (depois podemos extrair EXIF)
        # Coordenadas do centro do Brasil como padrão
        return {
            'filename': filename,
            'original_url': url,
            'thumbnail': f'/thumbnail/{thumb_filename}',
            'full_image': url,
            'latitude': -15.7942 + (hash(filename) % 100 - 50) / 1000,  # Variação pequena
            'longitude': -47.8822 + (hash(filename) % 100 - 50) / 1000,
            'data_tirada': datetime.now().strftime('%Y-%m-%d'),
            'processed_at': time.time()
        }
        
    except Exception as e:
        print(f"❌ Erro ao processar {filename}: {e}")
        return None

def processar_kml_simples(kml_url, filename):
    """Processa KML de forma simplificada"""
    try:
        print(f"🗺️ Processando KML: {filename}")
        
        response = requests.get(kml_url, timeout=30)
        if response.status_code != 200:
            return []
        
        content = response.text
        
        # Extrair coordenadas de forma simples (para KMLs básicos)
        import re
        
        trajetos = []
        coordinates_pattern = r'<coordinates>([^<]+)</coordinates>'
        name_pattern = r'<name>([^<]+)</name>'
        
        name_match = re.search(name_pattern, content)
        name = name_match.group(1) if name_match else filename
        
        coords_matches = re.findall(coordinates_pattern, content, re.DOTALL)
        
        for coords_str in coords_matches:
            coordenadas = []
            for line in coords_str.strip().split('\n'):
                for coord in line.strip().split():
                    parts = coord.split(',')
                    if len(parts) >= 2:
                        try:
                            lon, lat = float(parts[0]), float(parts[1])
                            coordenadas.append([lat, lon])
                        except:
                            continue
            
            if len(coordenadas) > 1:
                trajetos.append({
                    'type': 'LineString',
                    'name': name,
                    'filename': filename,
                    'coordinates': coordenadas,
                    'color': '#FF0000',
                    'weight': 3,
                    'opacity': 0.7
                })
        
        print(f"  ✅ {len(trajetos)} trajeto(s) encontrado(s)")
        return trajetos
        
    except Exception as e:
        print(f"❌ Erro ao processar KML: {e}")
        return []

def processar_todas_fotos():
    """Processa todas as fotos e KMLs"""
    print("🔄 Iniciando processamento...")
    
    # Listar arquivos do GitHub
    arquivos = listar_arquivos_github_com_cache()
    
    if not arquivos:
        print("⚠️  Nenhum arquivo encontrado")
        return {'fotos': [], 'trajetos': []}
    
    fotos = []
    trajetos = []
    
    # Processar cada arquivo
    for i, arquivo in enumerate(arquivos):
        filename = arquivo['name']
        url = get_github_raw_url(filename)
        
        print(f"[{i+1}/{len(arquivos)}] {filename}")
        
        # Processar imagens
        if filename.lower().endswith(('.jpg', '.jpeg', '.png', '.heic')):
            foto = processar_imagem_rapida(url, filename)
            if foto:
                fotos.append(foto)
        
        # Processar KMLs
        elif filename.lower().endswith(('.kml', '.kmz')):
            trajetos_kml = processar_kml_simples(url, filename)
            trajetos.extend(trajetos_kml)
    
    # Salvar cache
    cache_data = {
        'fotos': fotos,
        'trajetos': trajetos,
        'processed_at': time.time(),
        'total_files': len(arquivos)
    }
    
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Processamento concluído:")
    print(f"   📸 Fotos: {len(fotos)}")
    print(f"   🗺️  Trajetos: {len(trajetos)}")
    
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
        if os.path.exists(CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            if cache_age < 3600:  # 1 hora
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return jsonify(data.get('fotos', []))
        
        data = processar_todas_fotos()
        return jsonify(data.get('fotos', []))
        
    except Exception as e:
        print(f"❌ Erro em /api/fotos: {e}")
        return jsonify({'error': 'Erro interno', 'details': str(e)}), 500

@app.route('/api/kml')
def listar_kml():
    """Retorna trajetos KML"""
    try:
        if os.path.exists(CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            if cache_age < 3600:  # 1 hora
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return jsonify({'trajetos': data.get('trajetos', [])})
        
        data = processar_todas_fotos()
        return jsonify({'trajetos': data.get('trajetos', [])})
        
    except Exception as e:
        print(f"❌ Erro em /api/kml: {e}")
        return jsonify({'trajetos': []})

@app.route('/api/all')
def listar_tudo():
    """Retorna tudo de uma vez"""
    try:
        if os.path.exists(CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            if cache_age < 3600:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return jsonify(json.load(f))
        
        return jsonify(processar_todas_fotos())
        
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
    from PIL import Image
    img = Image.new('RGB', (300, 300), color='lightgray')
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/jpeg')

@app.route('/api/status')
def status():
    """Status do sistema"""
    try:
        arquivos = listar_arquivos_github_com_cache()
        
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
            'github_repo': GITHUB_REPO,
            'github_files': len(arquivos),
            'cache_exists': cache_exists,
            'cache_age_minutes': int(cache_age / 60),
            'fotos_cached': fotos_count,
            'trajetos_cached': trajetos_count,
            'thumbnails': len(os.listdir(THUMBNAIL_FOLDER)) if os.path.exists(THUMBNAIL_FOLDER) else 0
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh')
def refresh():
    """Força atualização do cache"""
    data = processar_todas_fotos()
    return jsonify({
        'success': True,
        'fotos': len(data.get('fotos', [])),
        'trajetos': len(data.get('trajetos', []))
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🗺️  Mapa de Fotos - Versão Otimizada")
    print("=" * 60)
    print(f"📁 Repositório: {GITHUB_REPO}")
    print(f"🔑 GitHub Token: {'Sim' if GITHUB_TOKEN else 'Não'}")
    print("\n🔄 Iniciando cache inicial...")
    
    # Carregar cache inicial
    try:
        data = processar_todas_fotos()
        print(f"📸 Fotos: {len(data.get('fotos', []))}")
        print(f"🗺️  Trajetos: {len(data.get('trajetos', []))}")
    except Exception as e:
        print(f"⚠️  Erro no cache inicial: {e}")
    
    print(f"\n🌐 Servidor rodando na porta {port}")
    print("📊 Status: http://localhost:{port}/api/status")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)