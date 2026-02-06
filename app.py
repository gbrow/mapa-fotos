import os
import requests
from flask import Flask, jsonify, send_file, send_from_directory
from flask_cors import CORS
import json
import time
import hashlib
from PIL import Image, ImageOps
from io import BytesIO
import exifread  # ADICIONE ESTE IMPORT

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

def extrair_coordenadas_exif(image_data):
    """Extrai coordenadas GPS dos metadados EXIF"""
    try:
        # Usar exifread para extrair metadados
        tags = exifread.process_file(image_data, details=False)
        
        # Função para converter coordenadas EXIF para decimal
        def converter_para_decimal(tag):
            try:
                degrees = tag.values[0].num / tag.values[0].den
                minutes = tag.values[1].num / tag.values[1].den
                seconds = tag.values[2].num / tag.values[2].den
                return degrees + (minutes / 60.0) + (seconds / 3600.0)
            except:
                return None
        
        # Extrair latitude
        latitude = None
        longitude = None
        
        if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
            latitude = converter_para_decimal(tags['GPS GPSLatitude'])
            longitude = converter_para_decimal(tags['GPS GPSLongitude'])
            
            # Ajustar para hemisfério sul/oeste
            if latitude is not None and longitude is not None:
                if 'GPS GPSLatitudeRef' in tags and tags['GPS GPSLatitudeRef'].values == 'S':
                    latitude = -latitude
                if 'GPS GPSLongitudeRef' in tags and tags['GPS GPSLongitudeRef'].values == 'W':
                    longitude = -longitude
        
        return latitude, longitude
        
    except Exception as e:
        print(f"⚠️  Erro ao extrair EXIF: {e}")
        return None, None

def extrair_data_exif(image_data):
    """Extrai data dos metadados EXIF"""
    try:
        tags = exifread.process_file(image_data, details=False)
        
        # Tentar vários campos de data
        date_fields = [
            'EXIF DateTimeOriginal',
            'Image DateTime',
            'EXIF DateTimeDigitized',
            'EXIF SubSecTimeOriginal'
        ]
        
        for field in date_fields:
            if field in tags:
                return str(tags[field])
        
        return None
    except:
        return None

def processar_imagem_com_exif(url, filename):
    """Processa imagem extraindo coordenadas EXIF reais"""
    try:
        print(f"📥 Processando: {filename}")
        
        # Baixar imagem
        response = requests.get(url, timeout=30, stream=True)
        if response.status_code != 200:
            print(f"  ❌ Erro ao baixar: {response.status_code}")
            return None
        
        # Ler imagem em memória
        img_bytes = BytesIO(response.content)
        
        # Extrair EXIF (precisa ler como bytes)
        img_bytes.seek(0)
        latitude, longitude = extrair_coordenadas_exif(img_bytes)
        
        # Extrair data
        img_bytes.seek(0)
        data_tirada = extrair_data_exif(img_bytes)
        
        # Se não tem coordenadas GPS, pular esta imagem
        if latitude is None or longitude is None:
            print(f"  ⚠️  Sem coordenadas GPS: {filename}")
            return None
        
        print(f"  📍 Coordenadas encontradas: {latitude:.6f}, {longitude:.6f}")
        
        # Gerar thumbnail
        img_bytes.seek(0)
        thumb_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        thumb_name = f"{thumb_hash}.jpg"
        thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_name)
        
        # Criar thumbnail se não existir
        if not os.path.exists(thumb_path):
            try:
                img_bytes.seek(0)
                img = Image.open(img_bytes)
                
                # Corrigir orientação EXIF
                img = ImageOps.exif_transpose(img)
                
                # Redimensionar
                img.thumbnail(THUMBNAIL_SIZE)
                
                # Converter formato se necessário
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Salvar thumbnail
                img.save(thumb_path, 'JPEG', quality=85, optimize=True)
                print(f"  ✅ Thumbnail criada")
                
            except Exception as e:
                print(f"  ⚠️  Erro ao criar thumbnail: {e}")
                thumb_name = None
        
        return {
            'filename': filename,
            'original_url': url,
            'thumbnail': f'/thumbnail/{thumb_name}' if thumb_name else None,
            'full_image': url,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'data_tirada': data_tirada or 'Data não disponível',
            'processed_at': time.time()
        }
        
    except Exception as e:
        print(f"❌ Erro ao processar {filename}: {e}")
        import traceback
        traceback.print_exc()
        return None

def processar_kml_simples(kml_url, filename):
    """Processa KML de forma simplificada"""
    try:
        print(f"🗺️ Processando KML: {filename}")
        
        response = requests.get(kml_url, timeout=30)
        if response.status_code != 200:
            return []
        
        content = response.text
        
        # Extrair coordenadas de forma simples
        import re
        
        trajetos = []
        
        # Buscar por Placemarks
        placemark_pattern = r'<Placemark>.*?</Placemark>'
        placemarks = re.findall(placemark_pattern, content, re.DOTALL)
        
        for placemark in placemarks:
            # Extrair nome
            name_match = re.search(r'<name>([^<]+)</name>', placemark)
            name = name_match.group(1) if name_match else filename
            
            # Extrair descrição
            desc_match = re.search(r'<description>([^<]+)</description>', placemark)
            description = desc_match.group(1) if desc_match else ''
            
            # Extrair coordenadas
            coords_match = re.search(r'<coordinates>([^<]+)</coordinates>', placemark, re.DOTALL)
            if coords_match:
                coordenadas = []
                coords_text = coords_match.group(1).strip()
                
                # Processar coordenadas
                for line in coords_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    for coord in line.split():
                        parts = coord.split(',')
                        if len(parts) >= 2:
                            try:
                                # KML: longitude, latitude, altitude
                                lon = float(parts[0])
                                lat = float(parts[1])
                                coordenadas.append([lat, lon])  # Leaflet: lat, lon
                            except ValueError:
                                continue
                
                if len(coordenadas) > 1:
                    trajetos.append({
                        'type': 'LineString',
                        'name': name,
                        'description': description,
                        'filename': filename,
                        'coordinates': coordenadas,
                        'color': '#FF0000',
                        'weight': 3,
                        'opacity': 0.7
                    })
                    print(f"  ✅ Trajeto '{name}' com {len(coordenadas)} pontos")
        
        return trajetos
        
    except Exception as e:
        print(f"❌ Erro ao processar KML {filename}: {e}")
        return []

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
    
    for filename in arquivos:
        url = get_github_raw_url(filename)
        
        # Processar imagens (APENAS JPG/JPEG que têm EXIF)
        if filename.lower().endswith(('.jpg', '.jpeg')):
            print(f"\n📸 Processando imagem: {filename}")
            foto = processar_imagem_com_exif(url, filename)
            if foto:
                fotos.append(foto)
                print(f"  ✅ Adicionada: {foto['latitude']:.6f}, {foto['longitude']:.6f}")
        
        # Processar KMLs
        elif filename.lower().endswith('.kml'):
            print(f"\n🗺️ Processando KML: {filename}")
            trajetos_kml = processar_kml_simples(url, filename)
            if trajetos_kml:
                trajetos.extend(trajetos_kml)
    
    # Se não encontrou fotos com EXIF, adicionar mensagem
    if len(fotos) == 0:
        print("\n⚠️  Nenhuma foto com coordenadas GPS encontrada!")
        print("   Certifique-se que suas fotos são JPG/JPEG com metadados EXIF de GPS")
    
    # Salvar cache
    cache_data = {
        'fotos': fotos,
        'trajetos': trajetos,
        'processed_at': time.time(),
        'total_files': len(arquivos),
        'image_count': len(fotos),
        'kml_count': len(trajetos)
    }
    
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Processamento concluído:")
    print(f"   📸 Fotos com GPS: {len(fotos)}")
    print(f"   🗺️  Trajetos KML: {len(trajetos)}")
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
            'fotos_com_gps': fotos_count,
            'trajetos_kml': trajetos_count,
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
    print("🗺️  MAPA DE FOTOS - COM EXTRATOR DE COORDENADAS GPS")
    print("=" * 60)
    print(f"📁 Repositório: {GITHUB_REPO}")
    print(f"🔑 Token GitHub: {'Sim' if GITHUB_TOKEN else 'Não (público)'}")
    print(f"🌐 Porta: {port}")
    print("=" * 60)
    
    # Cache inicial
    try:
        print("🔄 Criando cache inicial...")
        data = processar_arquivos()
        print(f"✅ Cache criado: {len(data.get('fotos', []))} fotos com GPS")
    except Exception as e:
        print(f"⚠️  Erro no cache inicial: {e}")
    
    print(f"\n🚀 Servidor pronto!")
    print(f"📊 Status: http://localhost:{port}/api/status")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)