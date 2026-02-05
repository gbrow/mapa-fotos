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

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, 'thumbnails')
CACHE_FILE = os.path.join(BASE_DIR, 'fotos_cache.json')
URLS_FILE = os.path.join(BASE_DIR, 'urls.json')

os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
THUMBNAIL_SIZE = (300, 300)

def corrigir_url(url):
    """Corrige URLs mal formatadas"""
    if not url or not isinstance(url, str):
        return None
    
    url = url.strip()
    
    # Lista de correções comuns
    correcoes = [
        (r'^https//', 'https://'),
        (r'^http//', 'http://'),
        (r'^https:/([^/])', r'https://\1'),
        (r'^http:/([^/])', r'http://\1'),
        (r'^//', 'https://'),  # URLs protocol-relative
    ]
    
    for padrao, substituicao in correcoes:
        if re.match(padrao, url):
            url = re.sub(padrao, substituicao, url)
            print(f"🔧 URL corrigida: {url[:50]}...")
    
    # Garantir que começa com protocolo
    if not url.startswith(('http://', 'https://')):
        print(f"⚠️  URL sem protocolo, adicionando https://: {url[:50]}...")
        url = 'https://' + url
    
    return url

def carregar_urls():
    """Carrega e valida URLs do arquivo"""
    try:
        if os.path.exists(URLS_FILE):
            with open(URLS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                urls = data.get('urls', [])
                
                # Corrigir todas as URLs
                urls_corrigidas = []
                for url in urls:
                    url_corrigida = corrigir_url(url)
                    if url_corrigida:
                        urls_corrigidas.append(url_corrigida)
                
                print(f"📋 URLs carregadas: {len(urls_corrigidas)} (após correção)")
                return urls_corrigidas
    except Exception as e:
        print(f"❌ Erro ao carregar URLs: {e}")
    
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
            print("❌ URL inválida após correção")
            return None
        
        # Configurar headers para evitar bloqueios
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/webp,image/*,*/*;q=0.8',
            'Referer': 'https://github.com/'
        }
        
        # Baixar imagem
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            print(f"❌ Erro HTTP {response.status_code} para {url[:50]}...")
            return None
        
        # Verificar conteúdo
        content_type = response.headers.get('content-type', '')
        if 'image' not in content_type:
            print(f"❌ Não é imagem ({content_type}): {url[:50]}...")
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
            print(f"⚠️  Sem coordenadas GPS: {filename}")
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
            'original_url': url,  # URL já corrigida
            'latitude': float(lat),
            'longitude': float(lon),
            'thumbnail': f'/thumbnail/{thumb_hash}',
            'full_image': url,  # URL original para imagem grande
            'data_tirada': str(tags.get('EXIF DateTimeOriginal', '')),
            'processed_at': time.time()
        }
        
    except requests.exceptions.RequestException as e:
        print(f"🌐 Erro de rede: {e}")
        return None
    except Exception as e:
        print(f"❌ Erro ao processar: {e}")
        return None

def processar_todas_fotos():
    """Processa todas as fotos"""
    urls = carregar_urls()
    
    if not urls:
        print("⚠️  Nenhuma URL configurada")
        return []
    
    print(f"🔗 URLs para processar: {len(urls)}")
    
    fotos = []
    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] Processando...")
        foto = baixar_e_processar_imagem(url)
        if foto:
            fotos.append(foto)
    
    # Salvar cache
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fotos, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Processadas: {len(fotos)} fotos")
    return fotos

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

@app.route('/thumbnail/<nome_arquivo>')
def servir_thumbnail(nome_arquivo):
    caminho = os.path.join(THUMBNAIL_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    return 'Thumbnail não encontrada', 404

@app.route('/api/refresh')
def refresh():
    return jsonify({'fotos': processar_todas_fotos()})

@app.route('/api/check-url/<path:url>')
def check_url(url):
    """Testa se uma URL está acessível"""
    try:
        url_corrigida = corrigir_url(url)
        response = requests.head(url_corrigida, timeout=10)
        return jsonify({
            'original': url,
            'corrected': url_corrigida,
            'accessible': response.status_code == 200,
            'status_code': response.status_code,
            'content_type': response.headers.get('content-type')
        })
    except Exception as e:
        return jsonify({'error': str(e), 'accessible': False})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🗺️  Mapa de Fotos com Correção de URLs")
    print("=" * 60)
    
    processar_todas_fotos()
    
    app.run(host='0.0.0.0', port=port, debug=False)