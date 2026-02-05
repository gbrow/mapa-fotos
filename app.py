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
def upload():
    """Página para upload de fotos"""
    if request.method == 'POST':
        if 'foto' not in request.files:
            return 'Nenhum arquivo selecionado'
        
        arquivo = request.files['foto']
        if arquivo.filename == '':
            return 'Nenhum arquivo selecionado'
        
        if arquivo and arquivo.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
            from werkzeug.utils import secure_filename
            filename = secure_filename(arquivo.filename)
            caminho = os.path.join(FOTOS_FOLDER, filename)
            arquivo.save(caminho)
            
            # Reprocessar fotos
            processar_fotos()
            
            return f'''
                <html>
                <body style="font-family: Arial; padding: 20px;">
                    <h1>✅ Upload realizado!</h1>
                    <p>Arquivo: <strong>{filename}</strong></p>
                    <p>A foto foi processada e aparecerá no mapa.</p>
                    <a href="/" style="display: inline-block; background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Voltar ao Mapa</a>
                    <br><br>
                    <a href="/upload" style="color: #667eea;">Enviar outra foto</a>
                </body>
                </html>
            '''
    
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Upload de Fotos</title>
        <style>
            body { font-family: Arial; padding: 40px; max-width: 500px; margin: 0 auto; }
            h1 { color: #333; }
            form { background: #f5f5f5; padding: 30px; border-radius: 10px; }
            input[type="file"] { padding: 10px; border: 2px dashed #ccc; width: 100%; }
            input[type="submit"] { background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 5px; cursor: pointer; margin-top: 15px; }
            a { color: #667eea; text-decoration: none; display: inline-block; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h1>📤 Upload de Fotos</h1>
        <p>Envie fotos com coordenadas GPS para aparecerem no mapa.</p>
        
        <form method="post" enctype="multipart/form-data">
            <input type="file" name="foto" accept=".jpg,.jpeg,.png" required>
            <br><br>
            <input type="submit" value="Enviar Foto">
        </form>
        
        <a href="/">← Voltar ao mapa</a>
        
        <div style="margin-top: 30px; padding: 15px; background: #e3f2fd; border-radius: 5px;">
            <h3>💡 Dicas:</h3>
            <ul>
                <li>Fotos devem ter metadados GPS</li>
                <li>Formatos aceitos: JPG, JPEG, PNG</li>
                <li>Tamanho máximo: 10MB</li>
                <li>Após upload, atualize a página do mapa</li>
            </ul>
        </div>
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