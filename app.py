import os
import requests
from flask import Flask, jsonify, send_file, send_from_directory
from flask_cors import CORS
import json
import time
import hashlib
from PIL import Image, ImageOps
from io import BytesIO
import exifread

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(BASE_DIR, 'fotos_cache.json')
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, 'thumbnails')
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)

# Configuração do GitHub - REPOSITÓRIO PÚBLICO
GITHUB_REPO = "gbrow/fotos-mapa"
GITHUB_BRANCH = "main"
# NÃO use token para repositórios públicos
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

def get_github_headers():
    """Headers para requests do GitHub - sem autenticação para repositórios públicos"""
    headers = {
        'User-Agent': 'MapaFotosApp/1.0',
        'Accept': 'application/vnd.github.v3+json'
    }
    # SÓ adicionar token se ele existir e for para repositório privado
    if GITHUB_TOKEN and GITHUB_TOKEN != '':
        headers['Authorization'] = f'token {GITHUB_TOKEN}'
        print("🔐 Usando token de autenticação")
    else:
        print("🌐 Cliente anônimo (repositório público)")
    return headers

def get_github_raw_url(filename):
    """Gera URL raw do GitHub para um arquivo - funciona para repositórios públicos"""
    return f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}/{filename}"

def get_github_api_url(path=""):
    """Gera URL da API do GitHub"""
    return f"https://api.github.com/repos/{GITHUB_REPO}/contents/{path}"

def listar_arquivos_github():
    """Lista arquivos do repositório GitHub - PARA REPOSITÓRIOS PÚBLICOS"""
    try:
        print(f"🔍 Conectando ao GitHub público: {GITHUB_REPO}")
        
        # Para repositórios públicos, não precisa de autenticação
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
            if isinstance(arquivos, list):
                for item in arquivos:
                    if isinstance(item, dict):
                        nome = item.get('name', '')
                        tipo = item.get('type', '')
                        if tipo == 'file':
                            nomes_arquivos.append(nome)
            elif isinstance(arquivos, dict):
                # Caso seja um único arquivo
                if arquivos.get('type') == 'file':
                    nomes_arquivos.append(arquivos.get('name', ''))
            
            print(f"📁 {len(nomes_arquivos)} arquivos encontrados")
            return nomes_arquivos
            
        elif response.status_code == 401:
            print("❌ Erro 401: Repositório privado sem token válido")
            print("   Soluções:")
            print("   1. Torne o repositório PÚBLICO")
            print("   2. Configure um token válido no Render")
            print("   3. Use a versão com dados fixos")
            return []
            
        elif response.status_code == 404:
            print(f"❌ Repositório não encontrado: {GITHUB_REPO}")
            print("   Verifique se o nome está correto")
            return []
            
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
        tags = exifread.process_file(image_data, details=False)
        
        def converter_para_decimal(tag):
            try:
                degrees = tag.values[0].num / tag.values[0].den
                minutes = tag.values[1].num / tag.values[1].den
                seconds = tag.values[2].num / tag.values[2].den
                return degrees + (minutes / 60.0) + (seconds / 3600.0)
            except:
                return None
        
        latitude = None
        longitude = None
        
        if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
            latitude = converter_para_decimal(tags['GPS GPSLatitude'])
            longitude = converter_para_decimal(tags['GPS GPSLongitude'])
            
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
        
        img_bytes = BytesIO(response.content)
        
        # Extrair EXIF
        img_bytes.seek(0)
        latitude, longitude = extrair_coordenadas_exif(img_bytes)
        
        # Extrair data
        img_bytes.seek(0)
        data_tirada = extrair_data_exif(img_bytes)
        
        # Se não tem coordenadas GPS, pular
        if latitude is None or longitude is None:
            print(f"  ⚠️  Sem coordenadas GPS: {filename}")
            return None
        
        print(f"  📍 Coordenadas: {latitude:.6f}, {longitude:.6f}")
        
        # Criar thumbnail
        thumb_hash = hashlib.md5(url.encode()).hexdigest()[:12]
        thumb_name = f"{thumb_hash}.jpg"
        thumb_path = os.path.join(THUMBNAIL_FOLDER, thumb_name)
        
        if not os.path.exists(thumb_path):
            try:
                img_bytes.seek(0)
                img = Image.open(img_bytes)
                img = ImageOps.exif_transpose(img)
                img.thumbnail((300, 300))
                
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                img.save(thumb_path, 'JPEG', quality=85, optimize=True)
                print(f"  ✅ Thumbnail criada")
            except Exception as e:
                print(f"  ⚠️  Erro thumbnail: {e}")
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
        return None

def processar_kml_simples(kml_url, filename):
    """Processa KML de forma simplificada"""
    try:
        print(f"🗺️ Processando KML: {filename}")
        
        response = requests.get(kml_url, timeout=30)
        if response.status_code != 200:
            return []
        
        content = response.text
        import re
        
        trajetos = []
        placemark_pattern = r'<Placemark>.*?</Placemark>'
        placemarks = re.findall(placemark_pattern, content, re.DOTALL)
        
        for placemark in placemarks:
            name_match = re.search(r'<name>([^<]+)</name>', placemark)
            name = name_match.group(1) if name_match else filename
            
            desc_match = re.search(r'<description>([^<]+)</description>', placemark)
            description = desc_match.group(1) if desc_match else ''
            
            coords_match = re.search(r'<coordinates>([^<]+)</coordinates>', placemark, re.DOTALL)
            if coords_match:
                coordenadas = []
                coords_text = coords_match.group(1).strip()
                
                for line in coords_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    for coord in line.split():
                        parts = coord.split(',')
                        if len(parts) >= 2:
                            try:
                                lon = float(parts[0])
                                lat = float(parts[1])
                                coordenadas.append([lat, lon])
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
        print(f"❌ Erro no KML {filename}: {e}")
        return []

def processar_arquivos():
    """Processa arquivos do GitHub público"""
    print("🔄 Processando arquivos...")
    
    arquivos = listar_arquivos_github()
    
    if not arquivos:
        print("⚠️  Nenhum arquivo encontrado no GitHub")
        print("   Verifique se o repositório existe e está público")
        return {'fotos': [], 'trajetos': []}
    
    fotos = []
    trajetos = []
    
    for filename in arquivos:
        url = get_github_raw_url(filename)
        
        if filename.lower().endswith(('.jpg', '.jpeg')):
            print(f"\n📸 Processando imagem: {filename}")
            foto = processar_imagem_com_exif(url, filename)
            if foto:
                fotos.append(foto)
        
        elif filename.lower().endswith('.kml'):
            print(f"\n🗺️ Processando KML: {filename}")
            trajetos_kml = processar_kml_simples(url, filename)
            if trajetos_kml:
                trajetos.extend(trajetos_kml)
    
    if len(fotos) == 0:
        print("\n⚠️  NENHUMA FOTO COM GPS ENCONTRADA!")
        print("   As fotos precisam ter metadados EXIF com coordenadas GPS")
        print("   Verifique se as fotos foram tiradas com GPS ativado")
    
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
    
    return cache_data

# Rotas da API (mantenha as mesmas)
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
                    data = json.load(f)
                    return jsonify(data.get('fotos', []))
        
        data = processar_arquivos()
        return jsonify(data.get('fotos', []))
        
    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/kml')
def listar_kml():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return jsonify({'trajetos': data.get('trajetos', [])})
        
        data = processar_arquivos()
        return jsonify({'trajetos': data.get('trajetos', [])})
        
    except Exception as e:
        return jsonify({'trajetos': []})

@app.route('/api/all')
def listar_tudo():
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        
        return jsonify(processar_arquivos())
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/thumbnail/<nome_arquivo>')
def servir_thumbnail(nome_arquivo):
    caminho = os.path.join(THUMBNAIL_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    
    img = Image.new('RGB', (300, 200), color='#f0f0f0')
    img_io = BytesIO()
    img.save(img_io, 'JPEG')
    img_io.seek(0)
    return send_file(img_io, mimetype='image/jpeg')

@app.route('/api/status')
def status():
    try:
        cache_exists = os.path.exists(CACHE_FILE)
        fotos_count = 0
        trajetos_count = 0
        
        if cache_exists:
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
            'repo_public': True,
            'cache_exists': cache_exists,
            'fotos_com_gps': fotos_count,
            'trajetos_kml': trajetos_count,
            'message': 'Repositório público - sem autenticação'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh')
def refresh():
    data = processar_arquivos()
    return jsonify({
        'success': True,
        'fotos': len(data.get('fotos', [])),
        'trajetos': len(data.get('trajetos', []))
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🗺️  MAPA DE FOTOS - VERSÃO PÚBLICA")
    print("=" * 60)
    print(f"📁 Repositório: {GITHUB_REPO}")
    print(f"🔒 Tipo: PÚBLICO (sem autenticação)")
    print(f"🌐 Porta: {port}")
    print("=" * 60)
    
    try:
        print("🔄 Inicializando...")
        data = processar_arquivos()
        print(f"✅ Pronto: {len(data.get('fotos', []))} fotos com GPS")
    except Exception as e:
        print(f"⚠️  Erro na inicialização: {e}")
    
    print(f"\n🚀 Servidor rodando!")
    print(f"📊 Status: /api/status")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)