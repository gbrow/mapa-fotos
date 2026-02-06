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
import xmltodict
import zipfile
import xml.etree.ElementTree as ET

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
            
            if isinstance(arquivos, dict):
                # Se for um único arquivo
                arquivos = [arquivos]
            
            if extensoes:
                arquivos = [f for f in arquivos 
                          if 'name' in f and any(f['name'].lower().endswith(ext) for ext in extensoes)]
            
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
        if isinstance(arquivo, dict) and arquivo.get('type') == 'file':
            url = get_github_raw_url(arquivo['name'])
            urls.append(url)
    
    print(f"📷 {len(urls)} imagens encontradas no GitHub")
    return urls

def extrair_coordenadas_kml(xml_content):
    """Extrai coordenadas de arquivo KML usando XML parsing"""
    trajetos = []
    
    try:
        # Tentar parse com xmltodict primeiro
        try:
            kml_dict = xmltodict.parse(xml_content)
            
            # Extrair Placemarks
            placemarks = []
            
            # Navegar pelo dicionário para encontrar Placemarks
            def find_placemarks(obj, path=""):
                if isinstance(obj, dict):
                    if 'Placemark' in obj:
                        placemarks.extend(obj['Placemark'] if isinstance(obj['Placemark'], list) else [obj['Placemark']])
                    
                    for key, value in obj.items():
                        find_placemarks(value, f"{path}.{key}")
                
                elif isinstance(obj, list):
                    for item in obj:
                        find_placemarks(item, path)
            
            find_placemarks(kml_dict)
            
            for placemark in placemarks:
                name = placemark.get('name', 'Trajeto')
                description = placemark.get('description', '')
                
                # Extrair LineString
                if 'LineString' in placemark:
                    coordinates_str = placemark['LineString'].get('coordinates', '')
                    if coordinates_str:
                        coordenadas = []
                        for coord in coordinates_str.strip().split():
                            parts = coord.split(',')
                            if len(parts) >= 2:
                                lon, lat = float(parts[0]), float(parts[1])
                                coordenadas.append([lat, lon])
                        
                        if len(coordenadas) > 1:
                            trajetos.append({
                                'type': 'LineString',
                                'name': name,
                                'description': description,
                                'coordinates': coordenadas,
                                'color': '#FF0000',
                                'weight': 4,
                                'opacity': 0.7,
                                'dashArray': '5, 5'
                            })
                
                # Extrair Point
                elif 'Point' in placemark:
                    coordinates_str = placemark['Point'].get('coordinates', '')
                    if coordinates_str:
                        parts = coordinates_str.strip().split(',')
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                            trajetos.append({
                                'type': 'Point',
                                'name': name,
                                'description': description,
                                'coordinates': [lat, lon],
                                'icon': '📍'
                            })
        
        except:
            # Fallback para ElementTree
            print("Usando ElementTree como fallback...")
            root = ET.fromstring(xml_content)
            
            # Namespace KML
            ns = {'kml': 'http://www.opengis.net/kml/2.2'}
            
            for placemark in root.findall('.//kml:Placemark', ns):
                name_elem = placemark.find('kml:name', ns)
                name = name_elem.text if name_elem is not None else 'Trajeto'
                
                desc_elem = placemark.find('kml:description', ns)
                description = desc_elem.text if desc_elem is not None else ''
                
                # LineString
                linestring = placemark.find('.//kml:LineString', ns)
                if linestring is not None:
                    coords_elem = linestring.find('kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        coordenadas = []
                        for coord in coords_elem.text.strip().split():
                            parts = coord.split(',')
                            if len(parts) >= 2:
                                lon, lat = float(parts[0]), float(parts[1])
                                coordenadas.append([lat, lon])
                        
                        if len(coordenadas) > 1:
                            trajetos.append({
                                'type': 'LineString',
                                'name': name,
                                'description': description,
                                'coordinates': coordenadas,
                                'color': '#FF0000',
                                'weight': 4,
                                'opacity': 0.7,
                                'dashArray': '5, 5'
                            })
                
                # Point
                point = placemark.find('.//kml:Point', ns)
                if point is not None:
                    coords_elem = point.find('kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        parts = coords_elem.text.strip().split(',')
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                            trajetos.append({
                                'type': 'Point',
                                'name': name,
                                'description': description,
                                'coordinates': [lat, lon],
                                'icon': '📍'
                            })
        
        print(f"✅ KML processado: {len(trajetos)} elementos")
        
    except Exception as e:
        print(f"❌ Erro ao processar KML: {e}")
        import traceback
        traceback.print_exc()
    
    return trajetos

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
        
        content = response.content
        
        # Verificar se é KMZ (arquivo ZIP)
        if kml_url.lower().endswith('.kmz'):
            with tempfile.NamedTemporaryFile(suffix='.kmz', delete=False) as temp_file:
                temp_file.write(content)
                temp_path = temp_file.name
            
            try:
                with zipfile.ZipFile(temp_path, 'r') as kmz:
                    # Encontrar arquivo KML dentro do KMZ
                    kml_files = [f for f in kmz.namelist() if f.lower().endswith('.kml')]
                    if kml_files:
                        with kmz.open(kml_files[0]) as kml_file:
                            content = kml_file.read()
            finally:
                os.unlink(temp_path)
        
        # Processar conteúdo KML
        trajetos = extrair_coordenadas_kml(content)
        
    except Exception as e:
        print(f"❌ Erro ao processar KML da URL: {e}")
    
    return trajetos

def carregar_kmls_automaticamente():
    """Carrega KMLs automaticamente do GitHub"""
    print("🔍 Buscando KMLs no GitHub...")
    
    # Listar arquivos KML/KMZ
    arquivos = listar_arquivos_github(['.kml', '.kmz'])
    
    todos_trajetos = []
    
    for arquivo in arquivos:
        if isinstance(arquivo, dict) and arquivo.get('type') == 'file':
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
    print("⚙️ Status: http://localhost:{port}/api/status")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)