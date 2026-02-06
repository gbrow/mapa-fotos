import os
import exifread
import requests
from flask import Flask, jsonify, send_file, send_from_directory, request
from flask_cors import CORS
from PIL import Image, ImageOps
import json
from io import BytesIO
import time
import re
import tempfile
from fastkml import kml
from fastkml.geometry import LineString, Point
import zipfile

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, 'thumbnails')
CACHE_FILE = os.path.join(BASE_DIR, 'fotos_cache.json')
URLS_FILE = os.path.join(BASE_DIR, 'urls.json')
KML_CACHE_FILE = os.path.join(BASE_DIR, 'kml_cache.json')

os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
THUMBNAIL_SIZE = (300, 300)

# Configuração do repositório GitHub
GITHUB_REPO = "gbrow/fotos-mapa"  # SEU REPOSITÓRIO AQUI
GITHUB_BRANCH = "main"

def get_github_raw_url(filename):
    """Gera URL raw do GitHub para um arquivo"""
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{filename}"

def get_github_api_url(path=""):
    """Gera URL da API do GitHub"""
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

def listar_arquivos_github(extensoes=None):
    """Lista arquivos do repositório GitHub"""
    try:
        response = requests.get(get_github_api_url(), timeout=10)
        if response.status_code == 200:
            arquivos = response.json()
            
            if extensoes:
                arquivos = [f for f in arquivos 
                          if any(f['name'].lower().endswith(ext) for ext in extensoes)]
            
            return arquivos
        else:
            print(f"❌ Erro GitHub API: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ Erro ao listar arquivos GitHub: {e}")
        return []

def carregar_urls_automaticamente():
    """Carrega URLs automaticamente do GitHub"""
    print("🔍 Buscando imagens no GitHub...")
    
    # Listar arquivos do GitHub
    arquivos = listar_arquivos_github(['.jpg', '.jpeg', '.png', '.heic'])
    
    urls = []
    for arquivo in arquivos:
        if arquivo['type'] == 'file':
            url = get_github_raw_url(arquivo['name'])
            urls.append(url)
    
    print(f"📷 {len(urls)} imagens encontradas no GitHub")
    return urls

def processar_kml_da_url(kml_url):
    """Processa KML de uma URL"""
    trajetos = []
    
    try:
        print(f"🗺️ Processando KML: {kml_url}")
        
        # Baixar arquivo
        response = requests.get(kml_url, timeout=30)
        if response.status_code != 200:
            print(f"❌ Erro ao baixar KML: {response.status_code}")
            return trajetos
        
        # Salvar temporariamente
        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.kml') as temp_file:
            temp_file.write(response.content)
            temp_path = temp_file.name
        
        # Processar KML
        trajetos = processar_kml_arquivo(temp_path)
        
        # Limpar arquivo temporário
        os.unlink(temp_path)
        
    except Exception as e:
        print(f"❌ Erro ao processar KML da URL: {e}")
    
    return trajetos

def processar_kml_arquivo(kml_path):
    """Processa arquivo KML/KMZ"""
    trajetos = []
    
    try:
        # Verificar se é KMZ
        if kml_path.lower().endswith('.kmz'):
            with zipfile.ZipFile(kml_path, 'r') as kmz:
                kml_files = [f for f in kmz.namelist() if f.lower().endswith('.kml')]
                if not kml_files:
                    return trajetos
                
                with kmz.open(kml_files[0]) as kml_file:
                    kml_content = kml_file.read()
                    k = kml.KML()
                    k.from_string(kml_content)
        else:
            with open(kml_path, 'rb') as f:
                kml_content = f.read()
                k = kml.KML()
                k.from_string(kml_content)
        
        # Extrair geometrias
        def extrair_geometrias(feature):
            geometrias = []
            
            if hasattr(feature, 'geometry') and feature.geometry:
                geometrias.append(feature.geometry)
            
            if hasattr(feature, 'features'):
                for subfeature in feature.features:
                    geometrias.extend(extrair_geometrias(subfeature))
            
            return geometrias
        
        # Processar features
        for document in k.features():
            for folder in document.features():
                geometrias = extrair_geometrias(folder)
                
                for geom in geometrias:
                    if isinstance(geom, LineString) and geom.coords:
                        coordenadas = []
                        for coord in geom.coords:
                            # KML: lon, lat, alt -> Leaflet: lat, lon
                            if len(coord) >= 2:
                                coordenadas.append([coord[1], coord[0]])
                        
                        if len(coordenadas) > 1:
                            trajetos.append({
                                'type': 'LineString',
                                'name': getattr(folder, 'name', 'Trajeto'),
                                'description': getattr(folder, 'description', ''),
                                'coordinates': coordenadas,
                                'color': '#FF0000',
                                'weight': 4,
                                'opacity': 0.7,
                                'dashArray': '5, 5'
                            })
                    
                    elif isinstance(geom, Point) and geom.coords:
                        trajetos.append({
                            'type': 'Point',
                            'name': getattr(folder, 'name', 'Ponto'),
                            'description': getattr(folder, 'description', ''),
                            'coordinates': [geom.coords[0][1], geom.coords[0][0]],
                            'icon': '📍'
                        })
        
        print(f"✅ KML processado: {len(trajetos)} elementos")
        
    except Exception as e:
        print(f"❌ Erro no processamento KML: {e}")
    
    return trajetos

def carregar_kmls_automaticamente():
    """Carrega KMLs automaticamente do GitHub"""
    print("🔍 Buscando KMLs no GitHub...")
    
    # Listar arquivos KML/KMZ
    arquivos = listar_arquivos_github(['.kml', '.kmz'])
    
    todos_trajetos = []
    
    for arquivo in arquivos:
        if arquivo['type'] == 'file':
            kml_url = get_github_raw_url(arquivo['name'])
            trajetos = processar_kml_da_url(kml_url)
            
            if trajetos:
                # Adicionar informação do arquivo fonte
                for trajeto in trajetos:
                    trajeto['source_file'] = arquivo['name']
                    trajeto['source_url'] = kml_url
                
                todos_trajetos.extend(trajetos)
                print(f"✅ {arquivo['name']}: {len(trajetos)} trajetos")
    
    # Salvar cache
    cache_data = {
        'trajetos': todos_trajetos,
        'source': 'github',
        'repo': GITHUB_REPO,
        'loaded_at': time.time()
    }
    
    with open(KML_CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    print(f"🗺️ Total de trajetos carregados: {len(todos_trajetos)}")
    return todos_trajetos

def corrigir_url(url):
    """Corrige URLs mal formatadas"""
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    
    # Corrigir https// para https://
    if url.startswith('https//'):
        url = 'https://' + url[7:]
    elif url.startswith('http//'):
        url = 'http://' + url[6:]
    
    # Garantir protocolo
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    return url

def carregar_urls():
    """Carrega URLs - tenta GitHub primeiro, depois arquivo local"""
    # Tentar carregar automaticamente do GitHub
    try:
        urls_github = carregar_urls_automaticamente()
        if urls_github:
            return urls_github
    except Exception as e:
        print(f"⚠️  Não foi possível carregar do GitHub: {e}")
        print("📁 Tentando arquivo local...")
    
    # Fallback para arquivo local
    try:
        if os.path.exists(URLS_FILE):
            with open(URLS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                urls = data.get('urls', [])
                return [corrigir_url(url) for url in urls if corrigir_url(url)]
    except Exception as e:
        print(f"❌ Erro ao carregar URLs locais: {e}")
    
    return []

def extrair_coordenadas(tags):
    """Extrai coordenadas GPS dos metadados EXIF"""
    def obter_gps_valor(tag):
        try:
            degrees = tag.values[0].num / tag.values[0].den
            minutes = tag.values[1].num / tag.values[1].den
            seconds = tag.values[2].num / tag.values[2].den
            return degrees + (minutes / 60.0) + (seconds / 3600.0)
        except:
            return None
    
    latitude = longitude = None
    
    if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
        latitude = obter_gps_valor(tags['GPS GPSLatitude'])
        longitude = obter_gps_valor(tags['GPS GPSLongitude'])
        
        if latitude is not None and longitude is not None:
            if 'GPS GPSLatitudeRef' in tags and tags['GPS GPSLatitudeRef'].values == 'S':
                latitude = -latitude
            if 'GPS GPSLongitudeRef' in tags and tags['GPS GPSLongitudeRef'].values == 'W':
                longitude = -longitude
    
    return latitude, longitude

def baixar_e_processar_imagem(url):
    """Baixa e processa uma imagem da URL"""
    try:
        print(f"📥 Processando: {url[:60]}...")
        
        # Validar URL
        url = corrigir_url(url)
        if not url:
            return None
        
        # Headers
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/*,*/*;q=0.8'
        }
        
        # Baixar
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            return None
        
        # Verificar tipo
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            return None
        
        # Nome do arquivo
        filename = os.path.basename(url.split('?')[0]) or f"foto_{hash(url)}.jpg"
        
        # Processar EXIF
        img_data = BytesIO(response.content)
        img_data.seek(0)
        tags = exifread.process_file(img_data, details=False)
        
        # Coordenadas
        lat, lon = extrair_coordenadas(tags)
        if lat is None or lon is None:
            return None
        
        # Thumbnail
        thumb_hash = f"thumb_{abs(hash(url))}.jpg"
        thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_hash)
        
        if not os.path.exists(thumb_path):
            img_data.seek(0)
            with Image.open(img_data) as img:
                try:
                    img = ImageOps.exif_transpose(img)
                except:
                    pass
                
                img.thumbnail(THUMBNAIL_SIZE)
                
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                img.save(thumb_path, 'JPEG', quality=85, optimize=True)
        
        return {
            'filename': filename,
            'original_url': url,
            'latitude': float(lat),
            'longitude': float(lon),
            'thumbnail': f'/thumbnail/{thumb_hash}',
            'full_image': url,
            'data_tirada': str(tags.get('EXIF DateTimeOriginal', '')),
            'processed_at': time.time()
        }
        
    except Exception as e:
        print(f"❌ Erro ao processar imagem: {e}")
        return None

def processar_todas_fotos():
    """Processa todas as fotos"""
    urls = carregar_urls()
    
    if not urls:
        print("⚠️  Nenhuma URL encontrada")
        return []
    
    print(f"🔗 Processando {len(urls)} URLs...")
    
    fotos = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] Processando...")
        foto = baixar_e_processar_imagem(url)
        if foto:
            fotos.append(foto)
    
    # Salvar cache
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fotos, f, indent=2, ensure_ascii=False)
    
    print(f"✅ {len(fotos)} fotos processadas")
    return fotos

def carregar_trajetos():
    """Carrega trajetos - tenta cache primeiro"""
    try:
        # Verificar cache recente (menos de 1 hora)
        if os.path.exists(KML_CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(KML_CACHE_FILE)
            if cache_age < 3600:
                with open(KML_CACHE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    print(f"🗺️ Trajetos carregados do cache ({len(data.get('trajetos', []))})")
                    return data.get('trajetos', [])
    except:
        pass
    
    # Carregar do GitHub
    return carregar_kmls_automaticamente()

# Rotas da API
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

@app.route('/api/fotos')
def listar_fotos():
    try:
        if os.path.exists(CACHE_FILE):
            cache_age = time.time() - os.path.getmtime(CACHE_FILE)
            if cache_age < 3600:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    return jsonify(json.load(f))
    except Exception as e:
        print(f"Cache error: {e}")
    
    return jsonify(processar_todas_fotos())

@app.route('/api/kml')
def listar_kml():
    return jsonify({'trajetos': carregar_trajetos()})

@app.route('/api/refresh')
def refresh_all():
    """Atualiza tudo"""
    fotos = processar_todas_fotos()
    trajetos = carregar_kmls_automaticamente()
    
    return jsonify({
        'fotos': len(fotos),
        'trajetos': len(trajetos),
        'message': 'Atualizado com sucesso'
    })

@app.route('/thumbnail/<nome_arquivo>')
def servir_thumbnail(nome_arquivo):
    caminho = os.path.join(THUMBNAIL_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    return 'Thumbnail não encontrada', 404

@app.route('/api/status')
def status():
    """Status do sistema"""
    urls = carregar_urls()
    trajetos = carregar_trajetos()
    
    return jsonify({
        'github_repo': GITHUB_REPO,
        'fotos_urls': len(urls),
        'fotos_cache': len(json.load(open(CACHE_FILE))) if os.path.exists(CACHE_FILE) else 0,
        'trajetos_kml': len(trajetos),
        'thumbnails': len(os.listdir(THUMBNAIL_FOLDER)) if os.path.exists(THUMBNAIL_FOLDER) else 0
    })

# Página de admin para configuração
@app.route('/admin')
def admin_page():
    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin - Configuração</title>
        <style>
            body {{ font-family: Arial; padding: 30px; max-width: 800px; margin: 0 auto; }}
            .card {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            .info {{ background: #e8f4fc; padding: 15px; border-radius: 5px; margin: 10px 0; }}
            .status-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin: 20px 0; }}
            .stat {{ background: white; padding: 15px; border-radius: 5px; text-align: center; }}
            .stat-value {{ font-size: 24px; font-weight: bold; color: #2c3e50; }}
            .stat-label {{ color: #7f8c8d; font-size: 14px; }}
            button {{ background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }}
            .btn-success {{ background: #2ecc71; }}
        </style>
    </head>
    <body>
        <h1>⚙️ Configuração do Sistema</h1>
        
        <div class="card">
            <h3>📊 Status Atual</h3>
            <div class="status-grid" id="status-grid">
                <!-- Preenchido por JavaScript -->
            </div>
        </div>
        
        <div class="card">
            <h3>🔄 Ações</h3>
            <button onclick="refreshAll()" class="btn-success">🔄 Atualizar Tudo (Fotos + KML)</button>
            <button onclick="clearCache()">🗑️ Limpar Cache</button>
            <a href="/" style="margin-left: 20px; color: #3498db;">🗺️ Voltar ao Mapa</a>
        </div>
        
        <div class="info">
            <h3>💡 Configuração Automática</h3>
            <p>O sistema está configurado para carregar automaticamente do repositório:</p>
            <p><strong>{GITHUB_REPO}</strong></p>
            <p>Ele buscará:</p>
            <ul>
                <li>📷 Todas as imagens (JPG, PNG, etc.)</li>
                <li>🗺️ Arquivos KML/KMZ com trajetos</li>
            </ul>
            <p>Para alterar o repositório, edite a variável <code>GITHUB_REPO</code> no código.</p>
        </div>
        
        <script>
            async function loadStatus() {{
                const response = await fetch('/api/status');
                const data = await response.json();
                
                document.getElementById('status-grid').innerHTML = `
                    <div class="stat">
                        <div class="stat-value">${{data.fotos_urls || 0}}</div>
                        <div class="stat-label">Fotos no GitHub</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">${{data.fotos_cache || 0}}</div>
                        <div class="stat-label">Fotos Processadas</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">${{data.trajetos_kml || 0}}</div>
                        <div class="stat-label">Trajetos KML</div>
                    </div>
                    <div class="stat">
                        <div class="stat-value">${{data.thumbnails || 0}}</div>
                        <div class="stat-label">Thumbnails</div>
                    </div>
                `;
            }}
            
            async function refreshAll() {{
                if (confirm('Isso irá reprocessar todas as fotos e trajetos. Continuar?')) {{
                    const response = await fetch('/api/refresh');
                    const data = await response.json();
                    alert(`✅ Atualizado!\\nFotos: ${{data.fotos}}\\nTrajetos: ${{data.trajetos}}`);
                    loadStatus();
                }}
            }}
            
            async function clearCache() {{
                if (confirm('Limpar todo o cache? As fotos serão reprocessadas na próxima vez.')) {{
                    await fetch('/api/refresh?_clear=1');
                    alert('Cache limpo!');
                    loadStatus();
                }}
            }}
            
            // Carregar status inicial
            loadStatus();
            // Atualizar a cada 30 segundos
            setInterval(loadStatus, 30000);
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🗺️  Mapa de Fotos - Carregamento Automático do GitHub")
    print("=" * 60)
    print(f"📁 Repositório: {GITHUB_REPO}")
    print(f"🌐 Branch: {GITHUB_BRANCH}")
    print("\n🔄 Iniciando carregamento automático...")
    
    # Carregar fotos
    fotos = processar_todas_fotos()
    print(f"📸 Fotos carregadas: {len(fotos)}")
    
    # Carregar KMLs
    trajetos = carregar_trajetos()
    print(f"🗺️ Trajetos carregados: {len(trajetos)}")
    
    print(f"\n🌐 Servidor rodando na porta {port}")
    print("⚙️ Admin: http://localhost:{port}/admin")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)