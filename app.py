import sys
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
import os
import exifread
from flask import Flask, jsonify, send_file, send_from_directory, request
from flask_cors import CORS
from PIL import Image, ImageOps
import json

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configurações
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FOTOS_FOLDER = os.path.join(BASE_DIR, 'fotos')
THUMBNAIL_FOLDER = os.path.join(BASE_DIR, 'thumbnails')
CACHE_FILE = os.path.join(BASE_DIR, 'fotos_cache.json')

# Criar pastas se não existirem
os.makedirs(THUMBNAIL_FOLDER, exist_ok=True)
os.makedirs(FOTOS_FOLDER, exist_ok=True)

THUMBNAIL_SIZE = (300, 300)

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
    
    latitude = None
    longitude = None
    
    if 'GPS GPSLatitude' in tags and 'GPS GPSLongitude' in tags:
        latitude = obter_gps_valor(tags['GPS GPSLatitude'])
        longitude = obter_gps_valor(tags['GPS GPSLongitude'])
        
        if latitude is not None and longitude is not None:
            if 'GPS GPSLatitudeRef' in tags and tags['GPS GPSLatitudeRef'].values == 'S':
                latitude = -latitude
            if 'GPS GPSLongitudeRef' in tags and tags['GPS GPSLongitudeRef'].values == 'W':
                longitude = -longitude
    
    return latitude, longitude

def processar_fotos():
    """Processa todas as fotos na pasta"""
    fotos_data = []
    
    if not os.path.exists(FOTOS_FOLDER):
        print(f"⚠️  Pasta 'fotos' não encontrada")
        return fotos_data
    
    arquivos = os.listdir(FOTOS_FOLDER)
    print(f"📁 Encontrados {len(arquivos)} arquivos")
    
    for filename in arquivos:
        if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            caminho = os.path.join(FOTOS_FOLDER, filename)
            
            try:
                with open(caminho, 'rb') as f:
                    tags = exifread.process_file(f, details=False)
                
                lat, lon = extrair_coordenadas(tags)
                
                if lat is not None and lon is not None:
                    # Criar thumbnail
                    thumb_path = os.path.join(THUMBNAIL_FOLDER, filename)
                    if not os.path.exists(thumb_path):
                        with Image.open(caminho) as img:
                            img = ImageOps.exif_transpose(img)
                            img.thumbnail(THUMBNAIL_SIZE)
                            if img.mode in ('RGBA', 'LA', 'P'):
                                img = img.convert('RGB')
                            img.save(thumb_path, 'JPEG', quality=85)
                    
                    fotos_data.append({
                        'filename': filename,
                        'latitude': float(lat),
                        'longitude': float(lon),
                        'thumbnail': f'/thumbnail/{filename}',
                        'full_image': f'/foto/{filename}',
                        'data_tirada': str(tags.get('EXIF DateTimeOriginal', ''))
                    })
                    
            except Exception as e:
                print(f"❌ Erro em {filename}: {e}")
    
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(fotos_data, f, ensure_ascii=False, indent=2)
    
    return fotos_data

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
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
    except:
        pass
    
    return jsonify(processar_fotos())

@app.route('/foto/<nome_arquivo>')
def servir_foto(nome_arquivo):
    caminho = os.path.join(FOTOS_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    return 'Foto não encontrada', 404

@app.route('/thumbnail/<nome_arquivo>')
def servir_thumbnail(nome_arquivo):
    caminho = os.path.join(THUMBNAIL_FOLDER, nome_arquivo)
    if os.path.exists(caminho):
        return send_file(caminho, mimetype='image/jpeg')
    
    caminho_original = os.path.join(FOTOS_FOLDER, nome_arquivo)
    if os.path.exists(caminho_original):
        return send_file(caminho_original, mimetype='image/jpeg')
    
    return 'Thumbnail não encontrada', 404

@app.route('/upload', methods=['GET', 'POST'])
def upload_simple():
    """Versão simplificada com múltiplos arquivos"""
    if request.method == 'POST':
        if 'fotos' not in request.files:
            return 'Nenhum arquivo selecionado'
        
        arquivos = request.files.getlist('fotos')
        contador = 0
        
        for arquivo in arquivos:
            if arquivo.filename != '':
                filename = secure_filename(arquivo.filename)
                arquivo.save(os.path.join(FOTOS_FOLDER, filename))
                contador += 1
        
        # Reprocessar tudo
        processar_fotos()
        
        return f'''
            <html>
            <body style="font-family: Arial; padding: 30px;">
                <h1>✅ Upload realizado!</h1>
                <p>{contador} foto(s) enviada(s) com sucesso.</p>
                <p>As fotos estão sendo processadas...</p>
                <br>
                <a href="/" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none;">Ver Mapa</a>
                <a href="/upload" style="background: #008CBA; color: white; padding: 10px 20px; text-decoration: none; margin-left: 10px;">Novo Upload</a>
            </body>
            </html>
        '''
    
    return '''
    <!DOCTYPE html>
    <html>
    <head><title>Upload Múltiplo</title></head>
    <body style="font-family: Arial; padding: 30px;">
        <h1>Upload de Múltiplas Fotos</h1>
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="fotos" multiple accept=".jpg,.jpeg,.png">
            <br><br>
            <input type="submit" value="Enviar Todas">
        </form>
        <p><small>Segure Ctrl (Windows) ou Cmd (Mac) para selecionar múltiplos arquivos</small></p>
    </body>
    </html>
    '''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🚀 Servidor Mapa de Fotos")
    print("=" * 60)
    print(f"📂 Pasta fotos: {FOTOS_FOLDER}")
    
    # Processar fotos existentes
    if os.path.exists(FOTOS_FOLDER):
        print("📸 Processando fotos...")
        fotos = processar_fotos()
        print(f"✅ {len(fotos)} fotos processadas")
    else:
        print("ℹ️  Pasta 'fotos' vazia")
        print("👉 Use /upload para enviar fotos")
    
    print(f"🌐 Acesse: http://localhost:{port}")
    print("📤 Upload: http://localhost:{port}/upload")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)